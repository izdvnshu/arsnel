"""Rich rendering for resume results."""

from __future__ import annotations

from rich.text import Text

from arsnel import ui
from arsnel.resume.analyzer import ResumeReport


def render_report(report: ResumeReport) -> None:
    ui.console.print(ui.panel(ui.score_bar(report.score), title="Match score"))
    if report.keyword_source == "heuristic":
        ui.console.print(
            "The model's keyword list was unreadable, so a frequency-based list was used.",
            style="muted",
        )

    table = ui.new_table("Keyword", "Status", title="Job keywords")
    for keyword in report.missing:
        table.add_row(Text(keyword), Text("missing", style="bold"))
    for keyword in report.matched:
        table.add_row(Text(keyword), Text("matched", style=ui.ROYAL_BLUE))
    ui.console.print(table)

    if report.bullets:
        ui.console.print(ui.panel(ui.bullet_list(report.bullets), title="Tailored bullet points"))
    else:
        ui.console.print("The model returned no bullet points. Try again or use a larger model.", style="muted")

    if report.unsupported:
        ui.console.print(
            ui.panel(
                ui.bullet_list(report.unsupported),
                title="Not supported by your resume (not added)",
            )
        )
