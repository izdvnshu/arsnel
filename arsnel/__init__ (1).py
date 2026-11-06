"""Folder organizer: extension + filename sorting, plus exact-duplicate detection."""

from arsnel.organizer.categories import Classification, Classifier
from arsnel.organizer.duplicates import DuplicateGroup, find_duplicates, hash_file
from arsnel.organizer.sorter import Move, SortResult, apply_moves, organize_file, plan_folder

__all__ = [
    "Classification",
    "Classifier",
    "DuplicateGroup",
    "Move",
    "SortResult",
    "apply_moves",
    "find_duplicates",
    "hash_file",
    "organize_file",
    "plan_folder",
]
