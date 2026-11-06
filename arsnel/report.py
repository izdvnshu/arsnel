"""Rich rendering for meeting notes."""

from __future__ import annotations

from rich.text import Text

from arsnel import ui
from arsnel.notes.summarizer import MeetingNotes


def render_notes(notes: MeetingNotes) -> None:
    ui.console.print(ui.panel(Text(notes.summary or "No summary produced."), title="Summary"))
    if notes.key_points:
        ui.console.print(ui.panel(ui.bullet_list(notes.key_points), title="Key points"))
    if notes.action_items:
        table = ui.new_table("#", "Action item", "Owner", "Due", title="Action items")
        for number, item in enumerate(notes.action_items, 1):
            table.add_row(str(number), Text(item.task), Text(item.owner or "-"), Text(item.due or "-"))
        ui.console.print(table)
    else:
        ui.console.print("No action items found.", style="muted")
