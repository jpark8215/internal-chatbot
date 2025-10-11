import argparse
import os
from pathlib import Path
from typing import Iterable, List

from .config import get_settings
from .dao import get_dao
from .embeddings import embed_texts_sync

# Optional parsers
try:
    from pypdf import PdfReader  # type: ignore
except Exception:  # pragma: no cover
    PdfReader = None

try:
    import docx  # python-docx  # type: ignore
except Exception:  # pragma: no cover
    docx = None


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_pdf_file(path: Path) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed. Install it to ingest PDFs: pip install pypdf")
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


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
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + chunk_size)
        chunk = text[start:end]
        # Prefer to cut at whitespace
        if end < n:
            ws = chunk.rfind("\n")
            if ws < 0:
                ws = chunk.rfind(" ")
            if ws > 200:  # only snap if it doesn't create tiny fragments
                end = start + ws
                chunk = text[start:end]
        chunks.append(chunk.strip())
        if end >= n:
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]


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
    settings = get_settings()
    dao = get_dao()

    total_chunks = 0
    for file_path in find_files(path):
        try:
            text = read_file_any(file_path)
        except Exception as e:
            print(f"[skip] Failed to read {file_path}: {e}")
            continue
        chunks = chunk_text(text)
        if not chunks:
            continue
        # Embed and insert in batches to avoid too many calls
        for chunk in chunks:
            vectors = embed_texts_sync([chunk], model=settings.embedding_model)
            dao.insert_document(content=chunk, embedding=vectors[0])
            total_chunks += 1
        print(f"[ok] {file_path} -> {len(chunks)} chunks")

    return total_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest files into pgvector using Ollama embeddings")
    parser.add_argument("path", help="Path to a file or directory to ingest")
    args = parser.parse_args()

    target = Path(args.path).expanduser()
    if not target.exists():
        raise SystemExit(f"Path not found: {target}")

    total = ingest_path(target)
    print(f"Ingested {total} chunks")


if __name__ == "__main__":
    main()
