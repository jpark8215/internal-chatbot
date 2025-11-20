import argparse
import os
import time
from pathlib import Path
from typing import Iterable, List, Tuple, Optional
from dataclasses import dataclass

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

try:
    from docling.document_converter import DocumentConverter  # type: ignore
    from docling.datamodel.base_models import InputFormat  # type: ignore
    DOCLING_AVAILABLE = True
except Exception:  # pragma: no cover
    DOCLING_AVAILABLE = False
    DocumentConverter = None


logger = get_logger(__name__)


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""
    chunk_index: int  # Index of chunk within the document (0-based)
    start_position: int  # Character position where chunk starts in original text
    end_position: int  # Character position where chunk ends in original text
    page_number: Optional[int] = None  # Page number (for PDFs, None for other formats)
    line_number: Optional[int] = None  # Line number (optional, for text files)

# Supported file extensions for ingestion
# Text formats
TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}

# Document formats (docling or fallback parsers)
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".html", ".htm"}

# Image formats (docling)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}

# Audio formats (docling - for transcription)
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac"}

# Excel formats (docling)
EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".xlsb"}

# All supported extensions
SUPPORTED_EXTENSIONS = (
    TEXT_EXTENSIONS | DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | 
    AUDIO_EXTENSIONS | EXCEL_EXTENSIONS
)


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_pdf_file(path: Path) -> Tuple[str, List[Tuple[int, int, int]]]:
    """
    Read PDF file and return text with page position mapping.
    
    Returns:
        Tuple of (full_text, page_positions) where page_positions is a list of
        (page_number, start_char, end_char) tuples indicating where each page starts/ends.
    """
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed. Install it to ingest PDFs: pip install pypdf")

    try:
        reader = PdfReader(str(path))
        pages = []
        page_positions = []  # List of (page_number, start_char, end_char)
        current_position = 0

        for page_num, page in enumerate(reader.pages):
            try:
                text = page.extract_text()
                if text and text.strip():
                    # Clean up the text
                    text = text.replace('\x00', '')  # Remove null characters
                    text = text.replace('\r', '\n')  # Normalize line endings
                    text = ' '.join(text.split())  # Normalize whitespace
                    
                    # Track page position
                    page_start = current_position
                    page_text = text
                    if pages:  # Add separator if not first page
                        page_text = "\n\n--- PAGE BREAK ---\n\n" + page_text
                        page_start = current_position + len("\n\n--- PAGE BREAK ---\n\n")
                    
                    pages.append(page_text)
                    page_end = page_start + len(text)
                    page_positions.append((page_num + 1, page_start, page_end))
                    current_position = page_end + len("\n\n--- PAGE BREAK ---\n\n") if pages else page_end
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1} of {path}: {e}")
                continue

        if not pages:
            logger.warning(f"No text extracted from PDF: {path}")
            return "", []

        # Join pages
        full_text = "".join(pages)

        # Add metadata
        try:
            metadata = reader.metadata
            if metadata:
                title = metadata.get('/Title', '')
                author = metadata.get('/Author', '')
                if title or author:
                    metadata_text = f"Document Title: {title}\nAuthor: {author}\n\n"
                    full_text = metadata_text + full_text
                    # Adjust page positions by metadata length
                    metadata_len = len(metadata_text)
                    page_positions = [(p, s + metadata_len, e + metadata_len) for p, s, e in page_positions]
        except Exception:
            pass  # Metadata extraction is optional

        return full_text, page_positions

    except Exception as e:
        logger.error(f"Failed to read PDF file {path}: {e}")
        raise


def read_docx_file(path: Path) -> str:
    if docx is None:
        raise RuntimeError("python-docx is not installed. Install it to ingest DOCX: pip install python-docx")
    d = docx.Document(str(path))
    return "\n".join(p.text for p in d.paragraphs)


def convert_to_markdown_with_docling(path: Path) -> str:
    """Convert document to Markdown using docling."""
    if not DOCLING_AVAILABLE or DocumentConverter is None:
        raise RuntimeError("docling is not installed. Install it to use Markdown conversion: pip install docling")
    
    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))
        
        # Extract markdown from the result
        # Docling typically returns a document with markdown content
        if hasattr(result, 'document'):
            doc = result.document
            if hasattr(doc, 'export_to_markdown'):
                return doc.export_to_markdown()
            elif hasattr(doc, 'text'):
                return doc.text
        elif hasattr(result, 'export_to_markdown'):
            return result.export_to_markdown()
        elif hasattr(result, 'text'):
            return result.text
        else:
            # Fallback: try to get markdown from the result dict/list
            if isinstance(result, dict) and 'markdown' in result:
                return result['markdown']
            elif isinstance(result, str):
                return result
            else:
                raise ValueError(f"Unexpected docling result format: {type(result)}")
    except Exception as e:
        logger.warning(f"Failed to convert {path} to Markdown with docling: {e}. Falling back to standard parser.")
        raise


def read_file_any(path: Path) -> Tuple[str, Optional[List[Tuple[int, int, int]]]]:
    """
    Read file and convert to Markdown using docling if available, otherwise use standard parsers.
    
    Returns:
        Tuple of (text, page_positions) where page_positions is None for non-PDF files,
        or a list of (page_number, start_char, end_char) for PDFs.
    """
    suffix = path.suffix.lower()
    
    # Docling-supported formats: documents, images, audio, Excel
    docling_formats = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | EXCEL_EXTENSIONS
    
    # Try docling first for supported formats
    if DOCLING_AVAILABLE and suffix in docling_formats:
        try:
            text = convert_to_markdown_with_docling(path)
            # Docling doesn't provide page positions, so return None
            return text, None
        except Exception as e:
            logger.debug(f"Docling conversion failed for {path}, using fallback: {e}")
            # Fall through to standard parsers
    
    # For text/markdown files, just read them (they're already in text format)
    if suffix in (".txt", ".md", ".markdown"):
        return read_text_file(path), None
    
    # Fallback to standard parsers for formats we can handle without docling
    if suffix == ".pdf":
        return read_pdf_file(path)  # Returns (text, page_positions)
    if suffix in (".docx",):
        return read_docx_file(path), None
    
    # If we get here and it's a docling format but docling failed, raise an error
    if suffix in docling_formats:
        raise RuntimeError(
            f"File format {suffix} requires docling for conversion, but docling conversion failed. "
            f"Install docling or use a different file format."
        )
    
    # Final fallback: try text
    return read_text_file(path), None


def chunk_text_recursive_markdown(text: str, chunk_size: int = 400, overlap: int = 0, 
                                   page_positions: Optional[List[Tuple[int, int, int]]] = None) -> List[Tuple[str, ChunkMetadata]]:
    """
    Recursive Character Chunker with Markdown separators and position tracking.
    
    This chunker prioritizes Markdown structure when splitting:
    1. Double newlines (paragraph breaks) - \n\n
    2. Single newlines (line breaks) - \n
    3. Spaces (word boundaries) - " "
    4. Any character (fallback) - ""
    
    Args:
        text: Text to chunk (should be Markdown format)
        chunk_size: Target chunk size in characters (default: 400)
        overlap: Overlap between chunks (default: 0)
        page_positions: Optional list of (page_number, start_char, end_char) for PDFs
    
    Returns:
        List of (chunk_text, ChunkMetadata) tuples
    """
    # Preprocess text
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text_length = len(text)
    
    # Markdown separators in order of priority
    separators = ["\n\n", "\n", " ", ""]
    
    def _get_page_number(position: int) -> Optional[int]:
        """Get page number for a given character position."""
        if not page_positions:
            return None
        for page_num, start_char, end_char in page_positions:
            if start_char <= position < end_char:
                return page_num
        # If position is beyond last page, return last page number
        if page_positions and position >= page_positions[-1][2]:
            return page_positions[-1][0]
        return None
    
    def _split_recursive(text_to_split: str, start_offset: int, separators_list: List[str]) -> List[Tuple[str, int, int]]:
        """Recursively split text using separators, returning (chunk, start_pos, end_pos)."""
        if not text_to_split or not text_to_split.strip():
            return []
        
        # If text is smaller than or equal to chunk_size, return as-is
        if len(text_to_split) <= chunk_size:
            chunk = text_to_split.strip()
            if chunk:
                return [(chunk, start_offset, start_offset + len(chunk))]
            return []
        
        # Try each separator in order
        for i, separator in enumerate(separators_list):
            if separator == "":
                # Last resort: split at character boundary
                chunks_list = []
                current_pos = start_offset
                for j in range(0, len(text_to_split), chunk_size):
                    chunk = text_to_split[j:j + chunk_size].strip()
                    if chunk:
                        chunk_start = current_pos + j
                        chunks_list.append((chunk, chunk_start, chunk_start + len(chunk)))
                return chunks_list
            
            # Split by this separator
            splits = text_to_split.split(separator)
            
            # If we got multiple splits, try to build chunks
            if len(splits) > 1:
                result = []
                current_chunk = ""
                current_pos = start_offset
                
                for j, split in enumerate(splits):
                    # Determine the text segment: split + separator (except for last split)
                    if j < len(splits) - 1:
                        segment = split + separator
                    else:
                        segment = split
                    
                    # Check if adding this segment would exceed chunk_size
                    if len(current_chunk) + len(segment) <= chunk_size:
                        current_chunk += segment
                    else:
                        # Save current chunk if it has content
                        if current_chunk.strip():
                            chunk_start = current_pos
                            chunk_end = chunk_start + len(current_chunk.strip())
                            result.append((current_chunk.strip(), chunk_start, chunk_end))
                            current_pos = chunk_end
                        
                        # If the segment itself is larger than chunk_size, recurse with next separator
                        if len(segment) > chunk_size:
                            remaining_separators = separators_list[i + 1:] if i + 1 < len(separators_list) else [""]
                            result.extend(_split_recursive(segment, current_pos, remaining_separators))
                            if result:
                                current_pos = result[-1][2]
                            current_chunk = ""
                        else:
                            current_chunk = segment
                            current_pos = current_pos  # Position stays same until we add to result
                
                # Add remaining chunk
                if current_chunk.strip():
                    chunk_start = current_pos
                    chunk_end = chunk_start + len(current_chunk.strip())
                    result.append((current_chunk.strip(), chunk_start, chunk_end))
                
                # Only return if we successfully created chunks
                if result:
                    return result
        
        # Fallback: shouldn't reach here, but just in case
        chunks_list = []
        for i in range(0, len(text_to_split), chunk_size):
            chunk = text_to_split[i:i + chunk_size].strip()
            if chunk:
                chunk_start = start_offset + i
                chunks_list.append((chunk, chunk_start, chunk_start + len(chunk)))
        return chunks_list
    
    # Split recursively
    chunk_data = _split_recursive(text, 0, separators)
    
    # Apply overlap if specified (though user wants 0 overlap)
    if overlap > 0 and len(chunk_data) > 1:
        overlapped_chunks = []
        for i, (chunk, start, end) in enumerate(chunk_data):
            if i == 0:
                overlapped_chunks.append((chunk, start, end))
            else:
                # Add overlap from previous chunk
                prev_chunk, prev_start, prev_end = chunk_data[i - 1]
                overlap_text = prev_chunk[-overlap:] if len(prev_chunk) >= overlap else prev_chunk
                new_chunk = overlap_text + chunk
                new_start = start - len(overlap_text)
                overlapped_chunks.append((new_chunk, new_start, end))
        chunk_data = overlapped_chunks
    
    # Convert to (chunk_text, ChunkMetadata) format
    result = []
    for chunk_index, (chunk_text, start_pos, end_pos) in enumerate(chunk_data):
        page_num = _get_page_number(start_pos)
        metadata = ChunkMetadata(
            chunk_index=chunk_index,
            start_position=start_pos,
            end_position=end_pos,
            page_number=page_num
        )
        result.append((chunk_text, metadata))
    
    return result


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 0, 
               page_positions: Optional[List[Tuple[int, int, int]]] = None) -> List[Tuple[str, ChunkMetadata]]:
    """
    Chunk text using Recursive Character Chunker with Markdown separators.
    
    This is the main chunking function that uses the Markdown-aware recursive chunker.
    
    Returns:
        List of (chunk_text, ChunkMetadata) tuples
    """
    return chunk_text_recursive_markdown(text, chunk_size=chunk_size, overlap=overlap, page_positions=page_positions)


def find_files(path: Path) -> Iterable[Path]:
    """Find all supported files in the given path."""
    if path.is_file():
        yield path
        return
    for root, _dirs, files in os.walk(path):
        for name in files:
            p = Path(root) / name
            if p.suffix.lower() in SUPPORTED_EXTENSIONS:
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
            file_type = file_path.suffix.lower()
            source_file = str(file_path.absolute())

            # Check if file was already ingested (basic check)
            existing_count = dao.count_documents_by_source()
            existing_files = {file_info[0] for file_info in existing_count}

            if source_file in existing_files:
                logger.info(f"Skipping already ingested file: {file_path}")
                continue

            # Get text and page positions (for PDFs)
            text, page_positions = read_file_any(file_path)
            
            chunks_with_metadata = chunk_text(text, chunk_size=settings.chunk_size, 
                                             overlap=settings.chunk_overlap, page_positions=page_positions)
            if not chunks_with_metadata:
                logger.warning(f"No chunks created from file: {file_path}")
                continue

            # Process chunks in batches for better performance
            batch_size = settings.embedding_batch_size
            documents_to_insert = []

            for i in range(0, len(chunks_with_metadata), batch_size):
                batch_chunks_with_metadata = chunks_with_metadata[i:i + batch_size]
                
                # Extract just the text for embedding
                batch_chunks = [chunk_txt for chunk_txt, _ in batch_chunks_with_metadata]

                # Get embeddings for batch
                embeddings = embed_texts_batch_sync(
                    batch_chunks,
                    model=settings.embedding_model,
                    max_concurrent=settings.max_concurrent_requests
                )

                # Prepare documents for batch insert with metadata
                for (chunk_txt, metadata), embedding in zip(batch_chunks_with_metadata, embeddings):
                    documents_to_insert.append((
                        chunk_txt, embedding, source_file, file_type,
                        metadata.chunk_index, metadata.start_position, 
                        metadata.end_position, metadata.page_number
                    ))

            # Insert all documents in a single transaction
            if documents_to_insert:
                dao.insert_documents_batch(documents_to_insert)
                total_chunks += len(documents_to_insert)

            file_duration = (time.time() - file_start_time) * 1000
            log_file_ingestion(
                logger,
                file_path,
                len(chunks_with_metadata),
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

            # Get text and page positions (for PDFs)
            text, page_positions = read_file_any(file_path)
            file_type = file_path.suffix.lower()

            chunks_with_metadata = chunk_text(text, chunk_size=settings.chunk_size, 
                                             overlap=settings.chunk_overlap, page_positions=page_positions)
            if not chunks_with_metadata:
                logger.warning(f"No chunks created from file: {file_path}")
                continue

            # Process chunks in batches
            batch_size = settings.embedding_batch_size
            documents_to_insert = []

            for i in range(0, len(chunks_with_metadata), batch_size):
                batch_chunks_with_metadata = chunks_with_metadata[i:i + batch_size]
                
                # Extract just the text for embedding
                batch_chunks = [chunk_txt for chunk_txt, _ in batch_chunks_with_metadata]

                embeddings = embed_texts_batch_sync(
                    batch_chunks,
                    model=settings.embedding_model,
                    max_concurrent=settings.max_concurrent_requests
                )

                for (chunk_txt, metadata), embedding in zip(batch_chunks_with_metadata, embeddings):
                    documents_to_insert.append((
                        chunk_txt, embedding, source_file, file_type,
                        metadata.chunk_index, metadata.start_position, 
                        metadata.end_position, metadata.page_number
                    ))

            if documents_to_insert:
                dao.insert_documents_batch(documents_to_insert)
                total_chunks += len(documents_to_insert)

            file_duration = (time.time() - file_start_time) * 1000
            log_file_ingestion(
                logger,
                file_path,
                len(chunks_with_metadata),
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
