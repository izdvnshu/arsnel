"""Plan and perform moves into category folders. Pure stdlib, easy to test."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from arsnel.organizer.categories import Classification, Classifier, get_extension

IGNORED_NAMES = frozenset({"desktop.ini", "thumbs.db", ".ds_store"})


@dataclass(frozen=True)
class Move:
    source: Path
    destination: Path
    classification: Classification


@dataclass(frozen=True)
class SortResult:
    move: Move
    moved: bool
    error: str | None = None


def should_skip(path: Path, ignore_extensions: Iterable[str] = ()) -> bool:
    """Hidden files, office lock files, OS metadata and in-progress downloads."""
    name = path.name
    if name.startswith((".", "~$")) or name.lower() in IGNORED_NAMES:
        return True
    ignored = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in ignore_extensions}
    return get_extension(name) in ignored


def unique_destination(dest: Path) -> Path:
    """Return `dest`, or `name (1).ext`, `name (2).ext`... if it already exists."""
    if not dest.exists():
        return dest
    ext = get_extension(dest.name)
    stem = dest.name[: -len(ext)] if ext else dest.name
    counter = 1
    while True:
        candidate = dest.with_name(f"{stem} ({counter}){ext}")
        if not candidate.exists():
            return candidate
        counter += 1


def plan_move(
    source: Path,
    root: Path,
    classifier: Classifier,
    ignore_extensions: Iterable[str] = (),
) -> Move | None:
    """Decide where `source` goes. Only direct children of `root` are considered."""
    if not source.is_file() or source.parent.resolve() != root.resolve():
        return None
    if should_skip(source, ignore_extensions):
        return None
    classification = classifier.classify(source.name)
    destination = unique_destination(root.joinpath(*classification.folder.split("/"), source.name))
    return Move(source, destination, classification)


def plan_folder(
    root: Path, classifier: Classifier, ignore_extensions: Iterable[str] = ()
) -> list[Move]:
    ignore = list(ignore_extensions)
    moves = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        move = plan_move(entry, root, classifier, ignore)
        if move is not None:
            moves.append(move)
    return moves


def execute_move(move: Move) -> SortResult:
    try:
        move.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(move.source), str(move.destination))
    except OSError as exc:  # locked, vanished, permission denied...
        return SortResult(move, False, str(exc))
    return SortResult(move, True)


def apply_moves(
    moves: Iterable[Move], on_progress: Callable[[SortResult], None] | None = None
) -> list[SortResult]:
    results = []
    for move in moves:
        result = execute_move(move)
        results.append(result)
        if on_progress:
            on_progress(result)
    return results


def organize_file(
    path: Path,
    root: Path,
    classifier: Classifier,
    ignore_extensions: Iterable[str] = (),
) -> SortResult | None:
    """Sort a single file (used by the watcher). Returns None if it should be left alone."""
    move = plan_move(path, root, classifier, ignore_extensions)
    return execute_move(move) if move else None
