"""
Document loaders.

The old RAG used four LangChain loaders, one of which (UnstructuredMarkdownLoader)
dragged in `unstructured` and with it effdet, opencv, google-cloud-vision, timm,
torchvision and pytesseract , to read markdown files. These are the same four
formats with their underlying libraries called directly.
"""

import logging
from pathlib import Path

log = logging.getLogger("core.rag")

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}


class UnsupportedDocument(ValueError):
    pass


def _load_pdf(path):
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"text": text, "page": number})
    return pages


def _load_docx(path):
    import docx

    document = docx.Document(str(path))
    blocks = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    # Tables carry a lot of the content in compliance documents; the old
    # Docx2txtLoader included them, so keep them.
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))
    text = "\n".join(blocks).strip()
    return [{"text": text, "page": 1}] if text else []


def _load_text(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace").strip()
    return [{"text": text, "page": 1}] if text else []


_LOADERS = {
    ".pdf": _load_pdf,
    ".docx": _load_docx,
    ".txt": _load_text,
    ".md": _load_text,
    ".markdown": _load_text,
}


def load_document(path):
    """
    Read one document into a list of {"text", "page"} sections.

    Raises UnsupportedDocument for anything else, so an unreadable upload fails
    the job with a clear reason instead of silently ingesting nothing.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    loader = _LOADERS.get(suffix)
    if loader is None:
        raise UnsupportedDocument(
            f"{path.name}: {suffix or 'no extension'} is not supported. "
            f"Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )

    sections = loader(path)
    log.info("Loaded %s: %d section(s)", path.name, len(sections))
    return sections
