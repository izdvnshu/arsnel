"""Compare a resume to a job description using a local model.

The model extracts keywords and drafts bullets; the match score itself is computed in
code (keyword coverage), so it is reproducible and does not depend on a small model's
arithmetic.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from arsnel.llm_client import LLMClient, LLMJSONError

MAX_RESUME_CHARS = 12_000
MAX_JD_CHARS = 8_000
MAX_KEYWORDS = 30

KEYWORD_SYSTEM = (
    "You are an ATS keyword analyst. Read the job description and list the concrete hiring "
    "keywords: hard skills, tools, technologies, frameworks, certifications, methodologies, "
    "domain terms and required qualifications. Use the short form a resume would use "
    "(1 to 3 words, e.g. 'Python', 'project management', 'AWS'). Skip soft-skill filler such "
    "as 'team player'. Respond with JSON only."
)

REWRITE_SYSTEM = (
    "You are a careful resume editor. Rewrite resume bullet points so they speak to a specific "
    "job description. Rules: use ONLY facts present in the resume; never invent employers, "
    "titles, dates, metrics, tools or certifications; work a missing keyword in only when the "
    "resume genuinely supports it; start each bullet with a strong action verb; keep each "
    "bullet under 30 words; include numbers only if the resume already contains them. "
    "Respond with JSON only."
)

_STOPWORDS = frozenset(
    """a about above after all also an and any are as at be been being but by can could do does
    each etc for from have has had if in into is it its may more most must need new no not of on
    or our out over own should so some such than that the their them then there these they this
    to up us use using want was we well were what when where which while who will with within
    work would you your able across experience ability including strong team role job years year
    required preferred responsibilities requirements skills knowledge working candidate""".split()
)


@dataclass
class ResumeReport:
    keywords: list[str]
    matched: list[str]
    missing: list[str]
    score: int
    bullets: list[str]
    unsupported: list[str] = field(default_factory=list)
    model: str = ""
    keyword_source: str = "model"  # "model" or "heuristic" (fallback)


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items = []
    for entry in value:
        text = str(entry.get("keyword") or entry.get("text") or "") if isinstance(entry, dict) else str(entry)
        text = text.strip().strip("-•* ").strip()
        if text:
            items.append(text)
    return items


def normalize_keywords(raw: list[str], limit: int = MAX_KEYWORDS) -> list[str]:
    """De-duplicate case-insensitively and drop empty or absurdly long entries."""
    seen: set[str] = set()
    cleaned = []
    for item in raw:
        keyword = " ".join(item.split())
        key = keyword.lower()
        if not keyword or len(keyword) > 40 or key in seen:
            continue
        seen.add(key)
        cleaned.append(keyword)
    return cleaned[:limit]


def keyword_in_text(keyword: str, text: str) -> bool:
    """Whole-token, case-insensitive match that treats space/hyphen alike and allows plurals."""
    base = keyword.strip().lower()
    if not base:
        return False
    variants = {base}
    if base.endswith("s") and len(base) > 3:
        variants.add(base[:-1])
    else:
        variants.add(base + "s")
    haystack = text.lower()
    for variant in variants:
        parts = [p for p in re.split(r"[\s\-]+", variant) if p]
        if not parts:
            continue
        body = r"[\s\-]+".join(re.escape(p) for p in parts)
        if re.search(rf"(?<![a-z0-9]){body}(?![a-z0-9])", haystack):
            return True
    return False


def score_keywords(keywords: list[str], resume_text: str) -> tuple[list[str], list[str], int]:
    matched = [k for k in keywords if keyword_in_text(k, resume_text)]
    missing = [k for k in keywords if k not in matched]
    score = round(100 * len(matched) / len(keywords)) if keywords else 0
    return matched, missing, score


def heuristic_keywords(job_description: str, limit: int = 20) -> list[str]:
    """Frequency-based fallback used only if the model's JSON cannot be parsed."""
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{1,}", job_description)
    counts = Counter(t.strip(".-").lower() for t in tokens)
    ranked = [w for w, _ in counts.most_common() if w and w not in _STOPWORDS and len(w) > 2]
    return ranked[:limit]


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit]


def extract_keywords(llm: LLMClient, job_description: str) -> tuple[list[str], str]:
    prompt = (
        f'JOB DESCRIPTION:\n"""\n{_clip(job_description, MAX_JD_CHARS)}\n"""\n\n'
        'Return JSON: {"keywords": ["up to 25 items, most important first"]}'
    )
    try:
        data = llm.chat_json(prompt, system=KEYWORD_SYSTEM)
    except LLMJSONError:
        return normalize_keywords(heuristic_keywords(job_description)), "heuristic"
    raw = data.get("keywords") if isinstance(data, dict) else data
    keywords = normalize_keywords(_as_str_list(raw))
    if not keywords:
        return normalize_keywords(heuristic_keywords(job_description)), "heuristic"
    return keywords, "model"


def rewrite_bullets(
    llm: LLMClient, resume_text: str, job_description: str, missing: list[str]
) -> tuple[list[str], list[str]]:
    prompt = (
        f'JOB DESCRIPTION:\n"""\n{_clip(job_description, MAX_JD_CHARS)}\n"""\n\n'
        f'RESUME:\n"""\n{_clip(resume_text, MAX_RESUME_CHARS)}\n"""\n\n'
        f"MISSING KEYWORDS (not found in the resume): {', '.join(missing) or 'none'}\n\n"
        "Return JSON with exactly this shape:\n"
        '{"bullets": ["5 to 8 tailored bullet points"], '
        '"unsupported_keywords": ["missing keywords the resume gives no honest basis for"]}'
    )
    data = llm.chat_json(prompt, system=REWRITE_SYSTEM)
    if not isinstance(data, dict):
        data = {}
    return _as_str_list(data.get("bullets")), _as_str_list(data.get("unsupported_keywords"))


def analyze(
    resume_text: str,
    job_description: str,
    llm: LLMClient,
    on_stage: Callable[[str], None] | None = None,
) -> ResumeReport:
    def stage(message: str) -> None:
        if on_stage:
            on_stage(message)

    stage("Extracting job keywords")
    keywords, source = extract_keywords(llm, job_description)
    matched, missing, score = score_keywords(keywords, resume_text)

    stage("Drafting tailored bullets")
    bullets, unsupported = rewrite_bullets(llm, resume_text, job_description, missing)
    return ResumeReport(
        keywords=keywords,
        matched=matched,
        missing=missing,
        score=score,
        bullets=bullets,
        unsupported=unsupported,
        model=llm.model,
        keyword_source=source,
    )


def to_markdown(report: ResumeReport, resume_name: str = "resume") -> str:
    lines = [
        "# Resume match report",
        "",
        f"Resume: `{resume_name}` · Model: `{report.model}`",
        "",
        f"**Match score: {report.score}%** ({len(report.matched)} of {len(report.keywords)} "
        "job keywords found in the resume)",
        "",
        "## Missing keywords",
        "",
    ]
    lines += [f"- {k}" for k in report.missing] or ["- none"]
    lines += ["", "## Matched keywords", ""]
    lines += [f"- {k}" for k in report.matched] or ["- none"]
    lines += ["", "## Tailored bullet points", ""]
    lines += [f"- {b}" for b in report.bullets] or ["- none generated"]
    if report.unsupported:
        lines += ["", "## Keywords your resume does not support yet", ""]
        lines += [f"- {k}" for k in report.unsupported]
    return "\n".join(lines) + "\n"
