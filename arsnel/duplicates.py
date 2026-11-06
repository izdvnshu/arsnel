"""Exact-duplicate detection: group by size first, then confirm with SHA-256."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class DuplicateGroup:
    digest: str
    size: int
    paths: tuple[Path, ...]

    @property
    def wasted_bytes(self) -> int:
        return self.size * (len(self.paths) - 1)


def hash_file(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    """SHA-256 of a file's contents, read in chunks so large files stay cheap."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(root: Path, recursive: bool = True) -> Iterator[Path]:
    """Regular files under `root`, skipping symlinks and anything inside hidden folders."""
    candidates = root.rglob("*") if recursive else root.iterdir()
    for path in candidates:
        try:
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root)
        except (OSError, ValueError):
            continue
        if any(part.startswith(".") for part in relative.parts):
            continue
        yield path


def find_duplicates(
    root: Path,
    *,
    recursive: bool = True,
    min_size: int = 1,
    progress: Callable[[int, int], None] | None = None,
) -> list[DuplicateGroup]:
    """Return groups of byte-identical files, largest reclaimable space first.

    Files with a unique size cannot be duplicates, so they are never hashed.
    `progress(done, total)` is called after each hashed file.
    """
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in iter_files(root, recursive):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size >= min_size:
            by_size[size].append(path)

    total = sum(len(paths) for paths in by_size.values() if len(paths) > 1)
    done = 0
    groups: list[DuplicateGroup] = []
    for size, paths in sorted(by_size.items()):
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for path in paths:
            try:
                by_hash[hash_file(path)].append(path)
            except OSError:
                pass  # unreadable file: ignore rather than abort the scan
            done += 1
            if progress:
                progress(done, total)
        for digest, same in by_hash.items():
            if len(same) > 1:
                groups.append(DuplicateGroup(digest, size, tuple(sorted(same))))

    groups.sort(key=lambda g: (-g.wasted_bytes, g.digest))
    return groups
