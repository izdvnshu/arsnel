from datetime import datetime

import pytest

from arsnel.notes.summarizer import (
    ActionItem,
    MeetingNotes,
    chunk_text,
    clean_subtitles,
    merge_locally,
    summarize,
    to_markdown,
)
from tests.fakes import FakeLLM, bad_json

NOTES = {
    "summary": "The team agreed to ship on Friday.",
    "key_points": ["Ship on Friday", "Budget approved"],
    "action_items": [
        {"task": "Send release notes", "owner": "Priya", "due": "Thursday"},
        {"task": "Book the demo room", "owner": "null", "due": ""},
        "Update the roadmap",
    ],
}


def test_chunk_text_respects_limit_and_keeps_content():
    text = "\n".join(f"line {i} " + "x" * 20 for i in range(50))
    chunks = chunk_text(text, max_chars=200)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    assert "".join(c.replace("\n", "") for c in chunks) == text.replace("\n", "")


def test_chunk_text_splits_one_huge_line():
    chunks = chunk_text("a" * 450, max_chars=200)
    assert [len(c) for c in chunks] == [200, 200, 50]


def test_chunk_text_empty():
    assert chunk_text("  \n ") == []


def test_clean_subtitles_removes_cues_and_timestamps():
    vtt = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\nHello team\n\n2\n00:00:04,000 --> 00:00:06,000\nLet's start\n"
    assert clean_subtitles(vtt) == "Hello team\n\nLet's start"


def test_summarize_single_chunk_parses_items():
    llm = FakeLLM([NOTES])
    notes = summarize("Alice: ship Friday.", llm)
    assert notes.summary.startswith("The team agreed")
    assert notes.parts == 1 and notes.model == "fake-model"
    assert [i.task for i in notes.action_items] == [
        "Send release notes",
        "Book the demo room",
        "Update the roadmap",
    ]
    assert notes.action_items[0] == ActionItem("Send release notes", "Priya", "Thursday")
    assert notes.action_items[1].owner == ""  # "null" is treated as empty


def test_summarize_multi_chunk_uses_merge_call():
    merged = {"summary": "Merged.", "key_points": [], "action_items": [{"task": "Only one"}]}
    llm = FakeLLM([NOTES, NOTES, merged])
    notes = summarize("a\n" * 300, llm, max_chars=300)
    assert notes.summary == "Merged."
    assert notes.parts >= 2
    assert len(llm.prompts) == notes.parts + 1


def test_summarize_multi_chunk_falls_back_to_local_merge():
    llm = FakeLLM([NOTES, NOTES, bad_json()])
    notes = summarize("a\n" * 200, llm, max_chars=300)
    # duplicates across parts collapse
    assert [i.task for i in notes.action_items].count("Send release notes") == 1
    assert notes.key_points == ["Ship on Friday", "Budget approved"]


def test_summarize_rejects_empty_transcript():
    with pytest.raises(ValueError):
        summarize("   ", FakeLLM([]))


def test_merge_locally_dedupes():
    a = MeetingNotes("A.", ["x"], [ActionItem("Do it")])
    b = MeetingNotes("B.", ["X", "y"], [ActionItem("do it"), ActionItem("Other")])
    merged = merge_locally([a, b])
    assert merged.summary == "A. B."
    assert merged.key_points == ["x", "y"]
    assert [i.task for i in merged.action_items] == ["Do it", "Other"]


def test_markdown_export_numbers_action_items():
    notes = MeetingNotes(
        "Summary text.",
        ["Point one"],
        [ActionItem("Send notes", "Priya", "Thursday"), ActionItem("Book room")],
        model="llama3.2",
    )
    markdown = to_markdown(notes, title="Weekly sync", source="sync.txt", generated=datetime(2026, 11, 5, 9, 30))
    assert markdown.startswith("# Weekly sync")
    assert "Source: `sync.txt` · Generated 2026-11-05 09:30 · Model: `llama3.2`" in markdown
    assert "1. Send notes (**Priya**, due Thursday)" in markdown
    assert "2. Book room\n" in markdown
    assert "## Key points" in markdown


def test_markdown_handles_no_action_items():
    assert "_No action items found._" in to_markdown(MeetingNotes("S."))
