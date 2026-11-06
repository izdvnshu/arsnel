"""Single entrypoint: `arsnel organize | resume | notes | init`."""

import os
import sys
from pathlib import Path
from typing import Annotated, NoReturn, Optional

import typer
from rich.text import Text

from arsnel import __version__, ui
from arsnel.config import Config, ConfigError, dump_default_config, load_config
from arsnel.env import has_loose_permissions, load_dotenv
from arsnel.llm_client import LLMClient, LLMError
from arsnel.notes import report as notes_report
from arsnel.notes import summarizer as notes_summarizer
from arsnel.organizer import report as organizer_report
from arsnel.organizer.categories import Classifier
from arsnel.organizer.duplicates import find_duplicates
from arsnel.organizer.sorter import apply_moves, plan_folder
from arsnel.resume import analyzer as resume_analyzer
from arsnel.resume import parser as resume_parser
from arsnel.resume import report as resume_report
from arsnel.utils import read_text_file, timestamped_path

ui.apply_typer_theme()

app = typer.Typer(
    name="arsnel",
    help="Local-first productivity automation: [bold]organize[/] files, tailor a [bold]resume[/], "
    "summarise meeting [bold]notes[/]. No accounts, no API keys.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


def _fail(message: str) -> NoReturn:
    ui.print_error(message)
    raise typer.Exit(code=1)


def _version(value: bool) -> None:
    if value:
        ui.console.print(f"arsnel {__version__}")
        raise typer.Exit()


def _cfg(ctx: typer.Context) -> Config:
    """Load config lazily so `arsnel init --config new.yaml` can create the file."""
    try:
        return load_config(ctx.obj["config_path"])
    except ConfigError as exc:
        _fail(str(exc))


def _llm(cfg: Config, model: Optional[str]) -> LLMClient:
    try:
        client = LLMClient.from_config(cfg.llm, model=model)
    except LLMError as exc:  # e.g. an API key configured for a plain-http remote host
        _fail(str(exc))
    if not client.is_local:
        ui.console.print(
            Text.assemble(
                ("warning", "bold reverse"),
                f" llm.host ({client.host}) is not this machine. "
                "Your resume and transcript text will be sent there.",
            )
        )
    try:
        with ui.console.status("Connecting to ollama", spinner="dots", spinner_style=ui.ROYAL_BLUE):
            client.check()
    except LLMError as exc:
        _fail(str(exc))
    return client


def _paste(label: str) -> str:
    """Read pasted text from stdin (works for pipes and interactive terminals)."""
    if sys.stdin.isatty():
        eof = "Ctrl+Z then Enter" if os.name == "nt" else "Ctrl+D"
        ui.console.print(f"Paste the {label}, then press {eof} on an empty line.", style="muted")
    text = sys.stdin.read().strip()
    if not text:
        _fail(f"No {label} received.")
    return text


def _saved(path: Path) -> Text:
    return Text.assemble(("saved ", ui.ROYAL_BLUE), str(path))


def _export(
    cfg: Config, content: str, *, stem: str, output: Optional[Path], force: bool
) -> None:
    if output is not None:
        target = output.expanduser()
    elif force or cfg.output.format == "markdown":
        target = timestamped_path(cfg.output.directory_path, stem)
    else:
        return
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        _fail(f"Could not write {target}: {exc}")
    ui.console.print(_saved(target))


@app.callback()
def main(
    ctx: typer.Context,
    config: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", envvar="ARSNEL_CONFIG", help="Path to config.yaml."),
    ] = None,
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version, is_eager=True, help="Show version and exit."),
    ] = None,
) -> None:
    env_file = load_dotenv()
    if env_file is not None and has_loose_permissions(env_file):
        ui.console.print(
            Text.assemble(
                ("warning", "bold reverse"),
                f" {env_file} is readable by other users. Run: chmod 600 {env_file}",
            )
        )
    ctx.obj = {"config_path": config}


@app.command()
def init(
    ctx: typer.Context,
    path: Annotated[Optional[Path], typer.Argument(help="Where to write the file. Default: ./config.yaml")] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing file.")] = False,
) -> None:
    """Write a starter [bold]config.yaml[/]."""
    target = (path or ctx.obj["config_path"] or Path("config.yaml")).expanduser()
    if target.exists() and not force:
        _fail(f"{target} already exists. Use --force to overwrite it.")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dump_default_config(), encoding="utf-8")
    except OSError as exc:
        _fail(f"Could not write {target}: {exc}")
    ui.console.print(_saved(target))


@app.command()
def organize(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path], typer.Argument(help="Folder to organize. Default: organizer.watch_dir.")
    ] = None,
    once: Annotated[bool, typer.Option("--once", help="Sort existing files, then exit.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show what would move; change nothing.")] = False,
    find_dupes: Annotated[
        bool, typer.Option("--find-duplicates", "-d", help="Report byte-identical files (SHA-256) and exit.")
    ] = False,
    recursive: Annotated[
        bool, typer.Option("--recursive/--flat", help="Include subfolders when finding duplicates.")
    ] = True,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip the confirmation prompt.")] = False,
) -> None:
    """Sort a folder into category subfolders, and keep watching it."""
    cfg = _cfg(ctx)
    root = (path or cfg.organizer.watch_path).expanduser()
    if not root.is_dir():
        _fail(f"Not a folder: {root}")
    root = root.resolve()
    ui.header("organize", str(root))

    if find_dupes:
        with ui.progress() as progress:
            task = progress.add_task("Hashing candidates", total=None)
            groups = find_duplicates(
                root,
                recursive=recursive,
                progress=lambda done, total: progress.update(task, total=total, completed=done),
            )
        organizer_report.render_duplicates(groups, root)
        return

    try:
        classifier = Classifier(cfg.organizer.extra_extensions, cfg.organizer.filename_rules)
    except ValueError as exc:
        _fail(f"Bad organizer settings in config: {exc}")
    ignore = cfg.organizer.ignore_extensions

    moves = plan_folder(root, classifier, ignore)
    if moves:
        organizer_report.render_plan(moves)
    else:
        ui.console.print("Nothing to sort right now.", style="muted")

    if dry_run:
        ui.console.print("Dry run: no files were moved.", style="muted")
        return

    if moves:
        if yes or typer.confirm("Move these files?", default=False):
            organizer_report.render_summary(apply_moves(moves))
        else:
            ui.console.print("Skipped existing files.", style="muted")

    if once:
        return

    from arsnel.organizer.watcher import watch

    ui.console.print(f"Watching {root}. Press Ctrl+C to stop.", style="accent")
    try:
        watch(
            root,
            classifier,
            ignore_extensions=ignore,
            settle_seconds=cfg.organizer.settle_seconds,
            on_result=organizer_report.render_result,
        )
    except KeyboardInterrupt:
        ui.console.print("\nStopped.", style="muted")


@app.command()
def resume(
    ctx: typer.Context,
    resume_file: Annotated[
        Path,
        typer.Argument(help="Resume file: .txt, .md, .pdf or .docx.", exists=True, dir_okay=False, readable=True),
    ],
    jd: Annotated[
        Optional[Path],
        typer.Option("--jd", "-j", help="Job description file. Omit to paste it.", exists=True, dir_okay=False),
    ] = None,
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="Override llm.model.")] = None,
    export: Annotated[bool, typer.Option("--export", "-e", help="Also save a Markdown report.")] = False,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Save the Markdown report here.")] = None,
) -> None:
    """Find missing keywords, rewrite bullets and score the match for a job."""
    cfg = _cfg(ctx)
    ui.header("resume", resume_file.name)
    try:
        resume_text = resume_parser.read_resume(resume_file)
    except (ValueError, OSError) as exc:
        _fail(str(exc))
    jd_text = read_text_file(jd).strip() if jd else _paste("job description")
    if not jd_text:
        _fail("The job description is empty.")

    llm = _llm(cfg, model)
    try:
        with ui.console.status("Starting", spinner="dots", spinner_style=ui.ROYAL_BLUE) as status:
            result = resume_analyzer.analyze(
                resume_text, jd_text, llm, on_stage=lambda message: status.update(message)
            )
    except LLMError as exc:
        _fail(str(exc))

    resume_report.render_report(result)
    _export(cfg, resume_analyzer.to_markdown(result, resume_file.name), stem=f"resume-{resume_file.stem}", output=output, force=export)


@app.command()
def notes(
    ctx: typer.Context,
    transcript: Annotated[
        Optional[Path],
        typer.Argument(help="Transcript file (.txt, .md, .vtt, .srt). Omit to paste.", exists=True, dir_okay=False),
    ] = None,
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="Override llm.model.")] = None,
    export: Annotated[bool, typer.Option("--export", "-e", help="Also save Markdown notes.")] = False,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Save the Markdown notes here.")] = None,
    title: Annotated[Optional[str], typer.Option("--title", "-t", help="Title for the exported notes.")] = None,
) -> None:
    """Summarise a meeting transcript into notes and numbered action items."""
    cfg = _cfg(ctx)
    ui.header("notes", transcript.name if transcript else "pasted transcript")
    if transcript:
        text = read_text_file(transcript)
        if transcript.suffix.lower() in {".srt", ".vtt"}:
            text = notes_summarizer.clean_subtitles(text)
    else:
        text = _paste("transcript")
    if not text.strip():
        _fail("The transcript is empty.")

    llm = _llm(cfg, model)
    try:
        with ui.console.status("Starting", spinner="dots", spinner_style=ui.ROYAL_BLUE) as status:
            result = notes_summarizer.summarize(
                text, llm, on_stage=lambda message: status.update(message)
            )
    except LLMError as exc:
        _fail(str(exc))

    notes_report.render_notes(result)
    markdown = notes_summarizer.to_markdown(
        result, title=title or "Meeting notes", source=transcript.name if transcript else None
    )
    _export(cfg, markdown, stem=f"notes-{transcript.stem if transcript else 'meeting'}", output=output, force=export)


if __name__ == "__main__":  # pragma: no cover
    app(prog_name="arsnel")
