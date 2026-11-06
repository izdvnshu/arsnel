"""Shared terminal styling: palette, dotted boxes and small rich helpers."""

from __future__ import annotations

from collections.abc import Iterable

from rich.box import Box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

WHITE = "#FFFFFF"
NEAR_BLACK = "#0A0A0A"
ROYAL_BLUE = "#4169E1"  # the sole accent colour

theme = Theme({"accent": ROYAL_BLUE, "accent.bold": f"bold {ROYAL_BLUE}", "muted": "dim"})
console = Console(theme=theme, highlight=False)
err_console = Console(theme=theme, stderr=True, highlight=False)

# Dotted frame used for every table and panel.
DOTTED = Box(
    "····\n"
    ": ::\n"
    "····\n"
    ": ::\n"
    "····\n"
    "····\n"
    ": ::\n"
    "····\n"
)


def header(command: str, detail: str = "") -> None:
    """Print the `ARSNEL · command` banner followed by a dotted rule."""
    line = Text.assemble(("ARSNEL", f"bold {ROYAL_BLUE}"), (" · ", "dim"), (command, "bold"))
    if detail:
        line.append(f"  {detail}", style="dim")
    console.print(line)
    console.print(Rule(characters="· ", style=ROYAL_BLUE))


def print_error(message: str) -> None:
    err_console.print(Text.assemble(("error", "bold reverse"), " ", message))


def panel(content: object, title: str | None = None) -> Panel:
    return Panel(
        content,  # type: ignore[arg-type]
        title=Text(title, style=f"bold {ROYAL_BLUE}") if title else None,
        title_align="left",
        box=DOTTED,
        border_style=ROYAL_BLUE,
        padding=(1, 2),
    )


def new_table(*headers: str, title: str | None = None) -> Table:
    table = Table(
        box=DOTTED,
        border_style=ROYAL_BLUE,
        header_style=f"bold {ROYAL_BLUE}",
        title=title,
        title_style="bold",
        title_justify="left",
    )
    for name in headers:
        table.add_column(name)
    return table


def bullet_list(items: Iterable[str], *, numbered: bool = False) -> Table:
    """A two-column grid so wrapped lines stay aligned under the text."""
    grid = Table.grid(padding=(0, 1), expand=True)
    grid.add_column(no_wrap=True, justify="right" if numbered else "left", style=ROYAL_BLUE)
    grid.add_column(ratio=1)
    for index, item in enumerate(items, 1):
        grid.add_row(f"{index}." if numbered else "·", Text(item))
    return grid


def score_bar(percent: int, width: int = 32) -> Text:
    filled = round(width * max(0, min(100, percent)) / 100)
    return Text.assemble(
        ("█" * filled, ROYAL_BLUE),
        ("·" * (width - filled), "dim"),
        (f"  {percent}%", "bold"),
    )


def progress(transient: bool = True) -> Progress:
    return Progress(
        SpinnerColumn(style=ROYAL_BLUE),
        TextColumn("{task.description}"),
        BarColumn(complete_style=ROYAL_BLUE, finished_style=ROYAL_BLUE, pulse_style=ROYAL_BLUE),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=transient,
    )


def apply_typer_theme() -> None:
    """Recolour typer's --help output to the ARSNEL palette (best effort)."""
    try:
        from typer import rich_utils
    except ImportError:  # pragma: no cover
        return
    styles = {
        "STYLE_OPTION": f"bold {ROYAL_BLUE}",
        "STYLE_SWITCH": f"bold {ROYAL_BLUE}",
        "STYLE_NEGATIVE_OPTION": f"bold {ROYAL_BLUE}",
        "STYLE_NEGATIVE_SWITCH": f"bold {ROYAL_BLUE}",
        "STYLE_METAVAR": "bold",
        "STYLE_USAGE": ROYAL_BLUE,
        "STYLE_REQUIRED_SHORT": ROYAL_BLUE,
        "STYLE_OPTIONS_PANEL_BORDER": ROYAL_BLUE,
        "STYLE_COMMANDS_PANEL_BORDER": ROYAL_BLUE,
        "STYLE_ERRORS_PANEL_BORDER": ROYAL_BLUE,
        "STYLE_COMMANDS_TABLE_FIRST_COLUMN": f"bold {ROYAL_BLUE}",
        "STYLE_ERRORS_SUGGESTION": "dim",
    }
    for name, value in styles.items():
        if hasattr(rich_utils, name):
            setattr(rich_utils, name, value)
