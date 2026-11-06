from pathlib import Path

import pytest

from arsnel.organizer.categories import Classifier, get_extension
from arsnel.organizer.sorter import (
    apply_moves,
    organize_file,
    plan_folder,
    should_skip,
    unique_destination,
)
from arsnel.organizer.watcher import wait_until_stable


@pytest.mark.parametrize(
    ("filename", "folder", "reason"),
    [
        ("holiday.jpg", "Images", "extension"),
        ("Screenshot 2026-01-01 at 10.00.png", "Images/Screenshots", "filename"),
        ("IMG_20260101.jpg", "Images/Camera", "filename"),
        ("WhatsApp Image 2026-01-01.jpeg", "Images/Messaging", "filename"),
        ("report.pdf", "Documents", "extension"),
        ("invoice_march.pdf", "Documents/Finance", "filename"),
        ("Tax-Returns-2025.xlsx", "Documents/Finance", "filename"),
        ("john_cv.docx", "Documents/Career", "filename"),
        ("Resume_2026.PDF", "Documents/Career", "filename"),
        ("syntax_guide.pdf", "Documents", "extension"),
        ("data.csv", "Spreadsheets", "extension"),
        ("backup.tar.gz", "Archives", "extension"),
        ("app-setup.zip", "Installers", "filename"),
        ("setup.exe", "Installers", "extension"),
        ("script.PY", "Code", "extension"),
        ("song.mp3", "Audio", "extension"),
        ("movie.mp4", "Videos", "extension"),
        ("screen-recording-1.mp4", "Videos/Screen Recordings", "filename"),
        ("mystery.xyz", "Other", "fallback"),
        ("noextension", "Other", "fallback"),
    ],
)
def test_classification(filename, folder, reason):
    result = Classifier().classify(filename)
    assert result.folder == folder
    assert result.reason == reason


def test_compound_extension():
    assert get_extension("Backup.TAR.GZ") == ".tar.gz"
    assert get_extension("photo.final.jpg") == ".jpg"


def test_filename_rule_only_applies_to_matching_category():
    # "invoice" in a music file must not be filed under Finance.
    assert Classifier().classify("invoice_jingle.mp3").folder == "Audio"


def test_custom_rules_override_defaults():
    classifier = Classifier(
        extra_extensions={"Ebooks": [".mobi", "azw"]},
        filename_rules=[{"pattern": "^meeting", "folder": "Work/Meetings"}],
    )
    assert classifier.classify("book.mobi").folder == "Ebooks"
    assert classifier.classify("book.azw").folder == "Ebooks"
    assert classifier.classify("meeting-notes.pdf").folder == "Work/Meetings"
    assert classifier.classify("resume.pdf").folder == "Documents/Career"


@pytest.mark.parametrize("folder", ["../escape", "/absolute", "C:/drive", ""])
def test_unsafe_custom_folders_are_rejected(folder):
    with pytest.raises(ValueError):
        Classifier(filename_rules=[{"pattern": "x", "folder": folder}])


def test_invalid_regex_is_rejected():
    with pytest.raises(ValueError):
        Classifier(filename_rules=[{"pattern": "(", "folder": "X"}])


def make(path: Path, content: bytes = b"x") -> Path:
    path.write_bytes(content)
    return path


def test_plan_does_not_touch_files(tmp_path):
    make(tmp_path / "photo.jpg")
    moves = plan_folder(tmp_path, Classifier())
    assert [m.destination for m in moves] == [tmp_path / "Images" / "photo.jpg"]
    assert (tmp_path / "photo.jpg").exists()
    assert not (tmp_path / "Images").exists()


def test_apply_moves_files_into_category_folders(tmp_path):
    make(tmp_path / "photo.jpg")
    make(tmp_path / "notes.txt")
    make(tmp_path / "invoice_may.pdf")
    results = apply_moves(plan_folder(tmp_path, Classifier()))
    assert all(r.moved for r in results)
    assert (tmp_path / "Images" / "photo.jpg").is_file()
    assert (tmp_path / "Documents" / "notes.txt").is_file()
    assert (tmp_path / "Documents" / "Finance" / "invoice_may.pdf").is_file()
    assert not (tmp_path / "photo.jpg").exists()


def test_name_collision_gets_numbered_suffix(tmp_path):
    (tmp_path / "Images").mkdir()
    make(tmp_path / "Images" / "photo.jpg", b"old")
    make(tmp_path / "photo.jpg", b"new")
    apply_moves(plan_folder(tmp_path, Classifier()))
    assert (tmp_path / "Images" / "photo.jpg").read_bytes() == b"old"
    assert (tmp_path / "Images" / "photo (1).jpg").read_bytes() == b"new"


def test_unique_destination_keeps_compound_extension(tmp_path):
    make(tmp_path / "backup.tar.gz")
    assert unique_destination(tmp_path / "backup.tar.gz").name == "backup (1).tar.gz"


def test_skips_hidden_partial_lock_and_directories(tmp_path):
    make(tmp_path / ".hidden.jpg")
    make(tmp_path / "video.mp4.crdownload")
    make(tmp_path / "~$draft.docx")
    make(tmp_path / "Thumbs.db")
    (tmp_path / "somefolder").mkdir()
    assert plan_folder(tmp_path, Classifier(), [".crdownload"]) == []


def test_should_skip_accepts_extensions_without_dot(tmp_path):
    assert should_skip(tmp_path / "a.part", ["part"])
    assert not should_skip(tmp_path / "a.pdf", ["part"])


def test_organize_file_ignores_files_outside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "sub").mkdir()
    nested = make(root / "sub" / "photo.jpg")
    assert organize_file(nested, root, Classifier()) is None
    assert nested.exists()


def test_organize_file_moves_single_file(tmp_path):
    photo = make(tmp_path / "photo.jpg")
    result = organize_file(photo, tmp_path, Classifier())
    assert result is not None and result.moved
    assert (tmp_path / "Images" / "photo.jpg").exists()


def test_organize_file_missing_file_is_noop(tmp_path):
    assert organize_file(tmp_path / "gone.jpg", tmp_path, Classifier()) is None


def test_wait_until_stable_returns_when_file_stops_changing(tmp_path):
    target = make(tmp_path / "download.bin", b"abc")
    sleeps = []
    assert wait_until_stable(target, 0.01, sleep=sleeps.append) is True
    assert len(sleeps) == 1


def test_wait_until_stable_false_for_missing_file(tmp_path):
    assert wait_until_stable(tmp_path / "nope", 0.01, sleep=lambda _: None) is False
