"""Read resume text from .txt, .md, .pdf or .docx files."""

from __future__ import annotations

from pathlib import Path

from arsnel.utils import read_text_file

SUPPORTED = (".txt", ".md", ".pdf", ".docx")


def read_resume(path: Path) -> str:
    """Return the plain text of a resume, or raise ValueError with a readable reason."""
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        text = read_text_file(path)
    elif suffix == ".pdf":
        text = _read_pdf(path)
    elif suffix == ".docx":
        text = _read_docx(path)
    else:
        raise ValueError(f"Unsupported resume format '{suffix}'. Use one of: {', '.join(SUPPORTED)}")
    text = text.strip()
    if not text:
        raise ValueError(
            f"No text could be extracted from {path.name}. "
            "Scanned PDFs need OCR first; try exporting a text-based PDF or a .docx."
        )
    return text


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx(path: Path) -> str:
    from docx import Document

    document = Document(str(path))
    lines = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            lines.extend(cell.text for cell in row.cells)
    return "\n".join(lines)
