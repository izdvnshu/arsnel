"""Turn a transcript into a summary and action items using a local model."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from arsnel.llm_client import LLMClient, LLMJSONError

DEFAULT_CHUNK_CHARS = 12_000
_EMPTY_VALUES = {"", "none", "null", "n/a", "na", "unassigned", "unknown", "tbd"}

NOTES_SYSTEM = (
    "You are a precise meeting secretary. Summarise transcripts faithfully. Never invent "
    "decisions, owners or deadlines: if the transcript does not state an owner or due date, "
    "leave that field empty. Respond with JSON only."
)

_SHAPE = (
    '{"summary": "3 to 6 sentence summary", '
    '"key_points": ["decisions and important facts"], '
    '"action_items": [{"task": "imperative sentence", "owner": "name or empty", "due": "date or empty"}]}'
)


@dataclass
class ActionItem:
    task: str
    owner: str = ""
    due: str = ""


@dataclass
class MeetingNotes:
    summary: str
    key_points: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    model: str = ""
    parts: int = 1


def clean_subtitles(text: str) -> str:
    """Strip WEBVTT/SRT headers, cue numbers and timestamps, keeping the spoken text."""
    timestamp = re.compile(r"^\s*\d{1,2}:\d{2}(:\d{2})?[.,]\d{1,3}\s*-->")
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("WEBVTT") or timestamp.match(line) or stripped.isdigit():
            continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def chunk_text(text: str, max_chars: int = DEFAULT_CHUNK_CHARS) -> list[str]:
    """Split on line boundaries so each chunk fits the model's context."""
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        while len(line) > max_chars:  # a single enormous line
            if current:
                chunks.append("".join(current))
                current, size = [], 0
            chunks.append(line[:max_chars])
            line = line[max_chars:]
        if size + len(line) > max_chars and current:
            chunks.append("".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line)
    if current:
        chunks.append("".join(current))
    return [c.strip() for c in chunks if c.strip()]


def _optional(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in _EMPTY_VALUES else text


def _parse(data: Any) -> MeetingNotes:
    if not isinstance(data, dict):
        data = {}
    key_points = [str(p).strip() for p in data.get("key_points") or [] if str(p).strip()]
    items = []
    for entry in data.get("action_items") or []:
        if isinstance(entry, dict):
            task = str(entry.get("task") or "").strip()
            if task:
                items.append(ActionItem(task, _optional(entry.get("owner")), _optional(entry.get("due"))))
        elif str(entry).strip():
            items.append(ActionItem(str(entry).strip()))
    return MeetingNotes(summary=str(data.get("summary") or "").strip(), key_points=key_points, action_items=items)


def _extract(llm: LLMClient, chunk: str) -> MeetingNotes:
    prompt = f'TRANSCRIPT:\n"""\n{chunk}\n"""\n\nReturn JSON with exactly this shape:\n{_SHAPE}'
    return _parse(llm.chat_json(prompt, system=NOTES_SYSTEM))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def merge_locally(parts: list[MeetingNotes]) -> MeetingNotes:
    """Model-free merge used if the consolidation call fails."""
    items: list[ActionItem] = []
    seen: set[str] = set()
    for part in parts:
        for item in part.action_items:
            if item.task.lower() not in seen:
                seen.add(item.task.lower())
                items.append(item)
    return MeetingNotes(
        summary=" ".join(p.summary for p in parts if p.summary),
        key_points=_dedupe([k for p in parts for k in p.key_points]),
        action_items=items,
    )


def _merge(llm: LLMClient, parts: list[MeetingNotes]) -> MeetingNotes:
    payload = json.dumps(
        [{"summary": p.summary, "key_points": p.key_points, "action_items": [asdict(i) for i in p.action_items]}
         for p in parts],
        ensure_ascii=False,
    )
    prompt = (
        "Below are notes extracted from consecutive parts of ONE meeting. Merge them into a single "
        "consolidated result: one summary, de-duplicated key points, and every distinct action item.\n\n"
        f"PARTS:\n{payload}\n\nReturn JSON with exactly this shape:\n{_SHAPE}"
    )
    try:
        merged = _parse(llm.chat_json(prompt, system=NOTES_SYSTEM))
    except LLMJSONError:
        return merge_locally(parts)
    return merged if merged.summary else merge_locally(parts)


def summarize(
    transcript: str,
    llm: LLMClient,
    *,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    on_stage: Callable[[str], None] | None = None,
) -> MeetingNotes:
    chunks = chunk_text(transcript, max_chars)
    if not chunks:
        raise ValueError("The transcript is empty.")
    parts = []
    for index, chunk in enumerate(chunks, 1):
        if on_stage:
            on_stage(f"Reading part {index}/{len(chunks)}" if len(chunks) > 1 else "Reading transcript")
        parts.append(_extract(llm, chunk))
    if len(parts) > 1:
        if on_stage:
            on_stage("Merging parts")
        notes = _merge(llm, parts)
    else:
        notes = parts[0]
    notes.model = llm.model
    notes.parts = len(chunks)
    return notes


def to_markdown(
    notes: MeetingNotes,
    *,
    title: str = "Meeting notes",
    source: str | None = None,
    generated: datetime | None = None,
) -> str:
    stamp = (generated or datetime.now()).strftime("%Y-%m-%d %H:%M")
    meta = [f"Generated {stamp}"]
    if source:
        meta.insert(0, f"Source: `{source}`")
    if notes.model:
        meta.append(f"Model: `{notes.model}`")
    lines = [f"# {title}", "", " · ".join(meta), "", "## Summary", "", notes.summary or "_No summary produced._", ""]
    if notes.key_points:
        lines += ["## Key points", ""] + [f"- {p}" for p in notes.key_points] + [""]
    lines += ["## Action items", ""]
    if notes.action_items:
        for number, item in enumerate(notes.action_items, 1):
            extras = []
            if item.owner:
                extras.append(f"**{item.owner}**")
            if item.due:
                extras.append(f"due {item.due}")
            suffix = f" ({', '.join(extras)})" if extras else ""
            lines.append(f"{number}. {item.task}{suffix}")
    else:
        lines.append("_No action items found._")
    return "\n".join(lines) + "\n"
