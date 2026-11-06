"""Small stdlib-only helpers shared across modules."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

_UNITS = ("B", "KB", "MB", "GB", "TB")


def human_size(num_bytes: int) -> str:
    """Format a byte count, e.g. 1536 -> '1.5 KB'."""
    size = float(num_bytes)
    for unit in _UNITS:
        if size < 1024 or unit == _UNITS[-1]:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{num_bytes} B"  # pragma: no cover - loop always returns


def timestamped_path(
    directory: Path, stem: str, suffix: str = ".md", now: datetime | None = None
) -> Path:
    """Build `<directory>/<safe-stem>-YYYYmmdd-HHMMSS<suffix>`."""
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in stem).strip("-")
    return directory / f"{safe or 'arsnel'}-{stamp}{suffix}"


def read_text_file(path: Path) -> str:
    """Read a text file as UTF-8, replacing undecodable bytes instead of failing."""
    return path.read_text(encoding="utf-8", errors="replace")
