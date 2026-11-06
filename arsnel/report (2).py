"""Rich rendering for organizer output."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text

from arsnel import ui
from arsnel.organizer.duplicates import DuplicateGroup
from arsnel.organizer.sorter import Move, SortResult
from arsnel.utils import human_size


def render_plan(moves: list[Move], title: str = "Planned moves") -> None:
    table = ui.new_table("File", "Destination", "Rule", title=f"{title} ({len(moves)})")
    for move in moves:
        table.add_row(
            Text(move.source.name),
            Text(f"{move.classification.folder}/"),
            Text(move.classification.reason, style="dim"),
        )
    ui.console.print(table)


def render_result(result: SortResult) -> None:
    name = result.move.source.name
    if result.moved:
        ui.console.print(
            Text.assemble(
                ("moved ", ui.ROYAL_BLUE),
                (name, "bold"),
                f"  ->  {result.move.classification.folder}/",
            )
        )
    else:
        ui.print_error(f"Could not move {name}: {result.error}")


def render_summary(results: list[SortResult]) -> None:
    moved = sum(r.moved for r in results)
    failed = len(results) - moved
    line = Text.assemble((f"{moved} moved", ui.ROYAL_BLUE))
    if failed:
        line.append(f" · {failed} failed", style="bold")
    ui.console.print(line)


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def render_duplicates(groups: list[DuplicateGroup], root: Path) -> None:
    if not groups:
        ui.console.print("No exact duplicates found.", style="accent")
        return
    table = ui.new_table("#", "Size", "SHA-256", "Files", title="Exact duplicates")
    for index, group in enumerate(groups, 1):
        files = "\n".join(_relative(p, root) for p in group.paths)
        table.add_row(str(index), human_size(group.size), group.digest[:12], Text(files))
    ui.console.print(table)
    redundant = sum(len(g.paths) - 1 for g in groups)
    reclaimable = sum(g.wasted_bytes for g in groups)
    ui.console.print(
        Text.assemble(
            (f"{len(groups)} groups", ui.ROYAL_BLUE),
            f" · {redundant} redundant files · {human_size(reclaimable)} reclaimable",
        )
    )
    ui.console.print("Nothing was deleted. Review the list and remove copies yourself.", style="muted")
