import argparse
import os
import time
from pathlib import Path
from typing import Iterable, List

from .config import get_settings
from .dao import get_dao
from .embeddings import embed_texts_batch_sync
from .logging_config import get_logger, log_file_ingestion

# Optional parsers
try:
    from pypdf import PdfReader  # type: ignore
except Exception:  # pragma: no cover
    PdfReader = None

try:
    import docx  # python-docx  # type: ignore
except Exception:  # pragma: no cover
    docx = None


logger = get_logger(__name__)


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_pdf_file(path: Path) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed. Install it to ingest PDFs: pip install pypdf")

    try:
        reader = PdfReader(str(path))
        pages = []

        for page_num, page in enumerate(reader.pages):
            try:
                text = page.extract_text()
                if text and text.strip():
                    # Clean up the text
                    text = text.replace('\x00', '')  # Remove null characters
                    text = text.replace('\r', '\n')  # Normalize line endings
                    text = ' '.join(text.split())  # Normalize whitespace
                    pages.append(text)
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1} of {path}: {e}")
                continue

        if not pages:
            logger.warning(f"No text extracted from PDF: {path}")
            return ""

        # Join pages with clear separators
        full_text = "\n\n--- PAGE BREAK ---\n\n".join(pages)

        # Add metadata
        try:
            metadata = reader.metadata
            if metadata:
                title = metadata.get('/Title', '')
                author = metadata.get('/Author', '')
                if title or author:
                    full_text = f"Document Title: {title}\nAuthor: {author}\n\n{full_text}"
        except Exception:
            pass  # Metadata extraction is optional

        return full_text

    except Exception as e:
        logger.error(f"Failed to read PDF file {path}: {e}")
        raise


def read_docx_file(path: Path) -> str:
    if docx is None:
        raise RuntimeError("python-docx is not installed. Install it to ingest DOCX: pip install python-docx")
    d = docx.Document(str(path))
    return "\n".join(p.text for p in d.paragraphs)


def read_file_any(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md", ".markdown"):
        return read_text_file(path)
    if suffix == ".pdf":
        return read_pdf_file(path)
    if suffix in (".docx",):
        return read_docx_file(path)
    # Fallback: try text
    return read_text_file(path)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Improved chunking strategy for better term preservation."""
    chunks: List[str] = []
    start = 0
    n = len(text)

    # Preprocess text for better chunking
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    while start < n:
        end = min(n, start + chunk_size)
        chunk = text[start:end]

        # Smart boundary detection
        if end < n:
            # Look for sentence boundaries first
            sentence_end = chunk.rfind('. ')
            if sentence_end > chunk_size * 0.7:  # If we found a sentence end in the last 30%
                end = start + sentence_end + 1
                chunk = text[start:end]
            else:
                # Look for paragraph boundaries
                para_end = chunk.rfind('\n\n')
                if para_end > chunk_size * 0.6:  # If we found a paragraph end in the last 40%
                    end = start + para_end
                    chunk = text[start:end]
                else:
                    # Look for line boundaries
                    line_end = chunk.rfind('\n')
                    if line_end > chunk_size * 0.5:  # If we found a line end in the last 50%
                        end = start + line_end
                        chunk = text[start:end]
                    else:
                        # Look for word boundaries
                        word_end = chunk.rfind(' ')
                        if word_end > chunk_size * 0.3:  # If we found a word end in the last 70%
                            end = start + word_end
                            chunk = text[start:end]

        # Clean and add chunk
        clean_chunk = chunk.strip()
        if clean_chunk:
            chunks.append(clean_chunk)

        if end >= n:
            break

        # Move start position with overlap
        start = max(0, end - overlap)

    return chunks


def find_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for root, _dirs, files in os.walk(path):
        for name in files:
            p = Path(root) / name
            if p.suffix.lower() in {".txt", ".md", ".markdown", ".pdf", ".docx"}:
                yield p


def ingest_path(path: Path) -> int:
    """Ingest files from a path with batch processing and metadata tracking."""
    settings = get_settings()
    dao = get_dao()

    total_chunks = 0
    start_time = time.time()

    for file_path in find_files(path):
        file_start_time = time.time()

        try:
            text = read_file_any(file_path)
            file_type = file_path.suffix.lower()
            source_file = str(file_path.absolute())

            # Check if file was already ingested (basic check)
            existing_count = dao.count_documents_by_source()
            existing_files = {file_info[0] for file_info in existing_count}

            if source_file in existing_files:
                logger.info(f"Skipping already ingested file: {file_path}")
                continue

            chunks = chunk_text(text)
            if not chunks:
                logger.warning(f"No chunks created from file: {file_path}")
                continue

            # Process chunks in batches for better performance
            batch_size = settings.embedding_batch_size
            documents_to_insert = []

            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]

                # Get embeddings for batch
                embeddings = embed_texts_batch_sync(
                    batch_chunks,
                    model=settings.embedding_model,
                    max_concurrent=settings.max_concurrent_requests
                )

                # Prepare documents for batch insert
                for chunk, embedding in zip(batch_chunks, embeddings):
                    documents_to_insert.append((chunk, embedding, source_file, file_type))

            # Insert all documents in a single transaction
            if documents_to_insert:
                dao.insert_documents_batch(documents_to_insert)
                total_chunks += len(documents_to_insert)

            file_duration = (time.time() - file_start_time) * 1000
            log_file_ingestion(
                logger,
                file_path,
                len(chunks),
                file_duration,
                file_type=file_type,
                source_file=source_file
            )

        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
            continue

    total_duration = (time.time() - start_time) * 1000
    logger.info(f"Ingestion completed: {total_chunks} chunks in {total_duration:.2f}ms")

    return total_chunks


def ingest_path_incremental(path: Path) -> int:
    """Incremental ingestion that only processes new or modified files."""
    settings = get_settings()
    dao = get_dao()

    total_chunks = 0
    start_time = time.time()

    # Get existing files and their modification times
    existing_files = {}
    for file_info in dao.count_documents_by_source():
        source_file = file_info[0]
        if source_file:
            try:
                file_path = Path(source_file)
                if file_path.exists():
                    existing_files[source_file] = file_path.stat().st_mtime
            except Exception:
                continue

    for file_path in find_files(path):
        file_start_time = time.time()
        source_file = str(file_path.absolute())

        try:
            # Check if file needs to be re-ingested
            current_mtime = file_path.stat().st_mtime
            if source_file in existing_files and existing_files[source_file] >= current_mtime:
                logger.debug(f"Skipping unchanged file: {file_path}")
                continue

            # Remove old documents from this file
            if source_file in existing_files:
                deleted_count = dao.delete_documents_by_source(source_file)
                logger.info(f"Removed {deleted_count} old chunks from {file_path}")

            text = read_file_any(file_path)
            file_type = file_path.suffix.lower()

            chunks = chunk_text(text)
            if not chunks:
                logger.warning(f"No chunks created from file: {file_path}")
                continue

            # Process chunks in batches
            batch_size = settings.embedding_batch_size
            documents_to_insert = []

            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]

                embeddings = embed_texts_batch_sync(
                    batch_chunks,
                    model=settings.embedding_model,
                    max_concurrent=settings.max_concurrent_requests
                )

                for chunk, embedding in zip(batch_chunks, embeddings):
                    documents_to_insert.append((chunk, embedding, source_file, file_type))

            if documents_to_insert:
                dao.insert_documents_batch(documents_to_insert)
                total_chunks += len(documents_to_insert)

            file_duration = (time.time() - file_start_time) * 1000
            log_file_ingestion(
                logger,
                file_path,
                len(chunks),
                file_duration,
                file_type=file_type,
                source_file=source_file,
                incremental=True
            )

        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
            continue

    total_duration = (time.time() - start_time) * 1000
    logger.info(f"Incremental ingestion completed: {total_chunks} chunks in {total_duration:.2f}ms")

    return total_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest files into pgvector using Ollama embeddings")
    parser.add_argument("path", help="Path to a file or directory to ingest")
    parser.add_argument("--incremental", action="store_true", help="Only ingest new or modified files")
    args = parser.parse_args()

    target = Path(args.path).expanduser()
    if not target.exists():
        raise SystemExit(f"Path not found: {target}")

    if args.incremental:
        total = ingest_path_incremental(target)
    else:
        total = ingest_path(target)

    print(f"Ingested {total} chunks")


if __name__ == "__main__":
    main()
