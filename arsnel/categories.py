"""Extension and filename heuristics that decide where a file belongs."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePath, PurePosixPath

EXTENSION_MAP: dict[str, tuple[str, ...]] = {
    "Images": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic",
               ".heif", ".svg", ".ico", ".raw", ".cr2", ".nef"),
    "Videos": (".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"),
    "Audio": (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus", ".aiff"),
    "Documents": (".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".pages", ".tex"),
    "Spreadsheets": (".xls", ".xlsx", ".xlsm", ".ods", ".csv", ".tsv", ".numbers"),
    "Presentations": (".ppt", ".pptx", ".odp", ".key"),
    "Books": (".epub", ".mobi", ".azw3", ".djvu"),
    "Archives": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".zst",
                 ".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst"),
    "Installers": (".exe", ".msi", ".msix", ".dmg", ".pkg", ".deb", ".rpm", ".appimage",
                   ".apk", ".iso"),
    "Code": (".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".hpp", ".cs",
             ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".sh", ".bat", ".ps1", ".sql",
             ".html", ".css", ".ipynb"),
    "Data": (".json", ".xml", ".yaml", ".yml", ".toml", ".db", ".sqlite", ".parquet", ".log"),
    "Fonts": (".ttf", ".otf", ".woff", ".woff2"),
    "Design": (".psd", ".ai", ".xd", ".fig", ".sketch", ".indd"),
}

COMPOUND_EXTENSIONS = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst")
FALLBACK_FOLDER = "Other"


@dataclass(frozen=True)
class Classification:
    folder: str  # relative, forward-slash separated, e.g. "Documents/Finance"
    category: str  # top-level folder
    reason: str  # "filename" | "extension" | "fallback"


@dataclass(frozen=True)
class FilenameRule:
    pattern: re.Pattern[str]
    folder: str
    categories: frozenset[str] | None = None  # only apply to these extension categories


def _word(body: str) -> re.Pattern[str]:
    """Match `body` as a standalone token inside a filename stem."""
    return re.compile(rf"(?<![a-z])(?:{body})(?![a-z])", re.IGNORECASE)


DEFAULT_FILENAME_RULES: tuple[FilenameRule, ...] = (
    FilenameRule(
        re.compile(r"^(screenshot|screen[ _-]?shot|snip(ping)?[ _-]?tool|screen[ _-]?capture)", re.I),
        "Images/Screenshots",
        frozenset({"Images"}),
    ),
    FilenameRule(
        re.compile(r"^(screen[ _-]?recording|screencast|screen[ _-]?capture)", re.I),
        "Videos/Screen Recordings",
        frozenset({"Videos"}),
    ),
    FilenameRule(
        _word(r"resume|résumé|curriculum[ _-]?vitae|cv"),
        "Documents/Career",
        frozenset({"Documents"}),
    ),
    FilenameRule(
        _word(r"(?:invoice|receipt|statement|payslip|tax)(?:es|s)?"),
        "Documents/Finance",
        frozenset({"Documents", "Spreadsheets"}),
    ),
    FilenameRule(
        _word(r"assignment|homework|lecture|syllabus|thesis|coursework"),
        "Documents/Study",
        frozenset({"Documents", "Presentations"}),
    ),
    FilenameRule(_word(r"whatsapp|telegram|signal"), "Images/Messaging", frozenset({"Images"})),
    FilenameRule(
        re.compile(r"^(img|dsc|dscn|pxl|pict)[ _-]?\d{3,}", re.I),
        "Images/Camera",
        frozenset({"Images"}),
    ),
    FilenameRule(_word(r"setup|installer|install"), "Installers", frozenset({"Archives"})),
)


def get_extension(filename: str) -> str:
    """Lower-cased extension, understanding compound ones such as `.tar.gz`."""
    lower = filename.lower()
    for compound in COMPOUND_EXTENSIONS:
        if lower.endswith(compound):
            return compound
    return PurePath(lower).suffix


def get_stem(filename: str, extension: str | None = None) -> str:
    ext = get_extension(filename) if extension is None else extension
    return filename[: -len(ext)] if ext else filename


def _norm_ext(ext: str) -> str:
    ext = ext.strip().lower()
    return ext if ext.startswith(".") else f".{ext}"


def _clean_folder(folder: str) -> str:
    """Validate a user-supplied folder: relative, no `..`, no drive letters."""
    cleaned = str(folder).replace("\\", "/").strip()
    path = PurePosixPath(cleaned.rstrip("/"))
    if not cleaned or cleaned.startswith("/") or ".." in path.parts or ":" in cleaned:
        raise ValueError(f"Unsafe or empty folder name: {folder!r}")
    return "/".join(path.parts)


class Classifier:
    """Maps a filename to a destination folder. User rules win over built-ins."""

    def __init__(
        self,
        extra_extensions: Mapping[str, Iterable[str]] | None = None,
        filename_rules: Iterable[Mapping[str, str]] | None = None,
    ) -> None:
        self._ext_to_category = {
            ext: category for category, exts in EXTENSION_MAP.items() for ext in exts
        }
        for category, exts in (extra_extensions or {}).items():
            folder = _clean_folder(category)
            for ext in exts:
                self._ext_to_category[_norm_ext(ext)] = folder

        rules: list[FilenameRule] = []
        for rule in filename_rules or ():
            try:
                pattern = re.compile(rule["pattern"], re.IGNORECASE)
                folder = _clean_folder(rule["folder"])
            except (KeyError, TypeError, re.error) as exc:
                raise ValueError(f"Invalid filename rule {rule!r}: {exc}") from exc
            rules.append(FilenameRule(pattern, folder))
        self._rules = [*rules, *DEFAULT_FILENAME_RULES]

    def classify(self, filename: str) -> Classification:
        ext = get_extension(filename)
        category = self._ext_to_category.get(ext)
        stem = get_stem(filename, ext)
        for rule in self._rules:
            if rule.categories is not None and category not in rule.categories:
                continue
            if rule.pattern.search(stem):
                return Classification(rule.folder, rule.folder.split("/")[0], "filename")
        if category:
            return Classification(category, category.split("/")[0], "extension")
        return Classification(FALLBACK_FOLDER, FALLBACK_FOLDER, "fallback")
