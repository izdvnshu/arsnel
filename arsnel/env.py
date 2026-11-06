"""Tiny .env loader (stdlib only) so secrets live in one ignored file, never in config or code."""

from __future__ import annotations

import os
import stat
from pathlib import Path

ENV_FILENAME = ".env"


def candidate_paths() -> list[Path]:
    """Lookup order: ./.env, then ~/.arsnel/.env."""
    return [Path.cwd() / ENV_FILENAME, Path.home() / ".arsnel" / ENV_FILENAME]


def parse_env(text: str) -> dict[str, str]:
    """Parse KEY=value lines. Supports comments, `export KEY=...` and quoted values."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not key.isidentifier():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        values[key] = value
    return values


def load_dotenv(path: Path | None = None) -> Path | None:
    """Load the first .env found into os.environ without overriding real environment variables."""
    for candidate in [path] if path else candidate_paths():
        if candidate is not None and candidate.is_file():
            for key, value in parse_env(candidate.read_text(encoding="utf-8")).items():
                os.environ.setdefault(key, value)
            return candidate
    return None


def has_loose_permissions(path: Path) -> bool:
    """True if other users on a POSIX system could read the file (chmod 600 fixes it)."""
    if os.name == "nt":
        return False
    try:
        return bool(path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO))
    except OSError:
        return False
