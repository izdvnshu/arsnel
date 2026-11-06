import pytest
from docx import Document
from pypdf import PdfWriter

from arsnel.resume.analyzer import (
    analyze,
    heuristic_keywords,
    keyword_in_text,
    normalize_keywords,
    score_keywords,
    to_markdown,
)
from arsnel.resume.parser import read_resume
from tests.fakes import FakeLLM, bad_json

RESUME = "Built REST APIs in Python and Node.js. Used Docker and C++ daily. Led project-management for 3 teams."


@pytest.mark.parametrize(
    ("keyword", "expected"),
    [
        ("Python", True),
        ("python", True),
        ("Node.js", True),
        ("C++", True),
        ("REST API", True),  # plural in resume
        ("project management", True),  # hyphen vs space
        ("Java", False),
        ("Go", False),
        ("Dock", False),  # no partial-word matches
    ],
)
def test_keyword_matching(keyword, expected):
    assert keyword_in_text(keyword, RESUME) is expected


def test_score_is_keyword_coverage():
    matched, missing, score = score_keywords(["Python", "Docker", "Kubernetes", "Terraform"], RESUME)
    assert matched == ["Python", "Docker"]
    assert missing == ["Kubernetes", "Terraform"]
    assert score == 50


def test_score_with_no_keywords_is_zero():
    assert score_keywords([], RESUME) == ([], [], 0)


def test_normalize_keywords_dedupes_and_trims():
    raw = ["Python", "python", "  AWS  ", "", "x" * 60, "Machine   Learning"]
    assert normalize_keywords(raw) == ["Python", "AWS", "Machine Learning"]


def test_heuristic_keywords_skip_stopwords():
    words = heuristic_keywords("You will use Kubernetes and Terraform. Kubernetes experience required.")
    assert words[0] == "kubernetes"
    assert "will" not in words and "and" not in words


def test_analyze_end_to_end_with_fake_model():
    llm = FakeLLM(
        [
            {"keywords": ["Python", "Docker", "Kubernetes", "Terraform"]},
            {"bullets": ["Built REST APIs in Python."], "unsupported_keywords": ["Terraform"]},
        ]
    )
    stages = []
    report = analyze(RESUME, "We need Python and Kubernetes.", llm, on_stage=stages.append)
    assert report.score == 50
    assert report.missing == ["Kubernetes", "Terraform"]
    assert report.bullets == ["Built REST APIs in Python."]
    assert report.unsupported == ["Terraform"]
    assert report.model == "fake-model"
    assert len(stages) == 2
    assert "Kubernetes, Terraform" in llm.prompts[1]  # missing keywords reach the rewrite prompt


def test_analyze_falls_back_to_heuristic_keywords_on_bad_json():
    llm = FakeLLM([bad_json(), {"bullets": ["b"]}])
    report = analyze(RESUME, "Python Python Docker Kubernetes needed", llm)
    assert report.keyword_source == "heuristic"
    assert "python" in [k.lower() for k in report.keywords]


def test_markdown_report_contains_sections():
    llm = FakeLLM([{"keywords": ["Python", "Kubernetes"]}, {"bullets": ["Did a thing."]}])
    markdown = to_markdown(analyze(RESUME, "jd", llm), "cv.pdf")
    assert "**Match score: 50%**" in markdown
    assert "## Missing keywords" in markdown and "- Kubernetes" in markdown
    assert "## Tailored bullet points" in markdown and "- Did a thing." in markdown


def test_read_text_resume(tmp_path):
    path = tmp_path / "cv.txt"
    path.write_text("  Jane Doe\nPython  ", encoding="utf-8")
    assert read_resume(path) == "Jane Doe\nPython"


def test_read_docx_resume_including_tables(tmp_path):
    path = tmp_path / "cv.docx"
    document = Document()
    document.add_paragraph("Jane Doe")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Skills"
    table.rows[0].cells[1].text = "Python, SQL"
    document.save(str(path))
    text = read_resume(path)
    assert "Jane Doe" in text and "Python, SQL" in text


def test_blank_pdf_raises_helpful_error(tmp_path):
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(ValueError, match="No text could be extracted"):
        read_resume(path)


def test_unsupported_format(tmp_path):
    path = tmp_path / "cv.odt"
    path.write_text("x")
    with pytest.raises(ValueError, match="Unsupported"):
        read_resume(path)
