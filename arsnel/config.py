"""One config file shared by every ARSNEL module."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

CONFIG_FILENAME = "config.yaml"
ENV_VAR = "ARSNEL_CONFIG"
OUTPUT_FORMATS = ("terminal", "markdown")


class ConfigError(ValueError):
    """Raised when the config file is missing, unreadable or invalid."""


@dataclass
class OrganizerConfig:
    watch_dir: str = "~/Downloads"
    settle_seconds: float = 2.0
    ignore_extensions: list[str] = field(
        default_factory=lambda: [".crdownload", ".part", ".partial", ".tmp", ".download"]
    )
    extra_extensions: dict[str, list[str]] = field(default_factory=dict)
    filename_rules: list[dict[str, str]] = field(default_factory=list)

    @property
    def watch_path(self) -> Path:
        return Path(self.watch_dir).expanduser()


@dataclass
class LLMConfig:
    model: str = "llama3.2"
    host: str = "http://localhost:11434"
    temperature: float = 0.2
    num_ctx: int = 8192


@dataclass
class OutputConfig:
    # "terminal": print only. "markdown": print and also save a .md file.
    format: str = "terminal"
    directory: str = "~/arsnel-output"

    @property
    def directory_path(self) -> Path:
        return Path(self.directory).expanduser()


@dataclass
class Config:
    organizer: OrganizerConfig = field(default_factory=OrganizerConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def _build(cls: type, data: Any) -> Any:
    """Create a section dataclass from a mapping, ignoring unknown keys."""
    if data is None:
        return cls()
    if not isinstance(data, dict):
        raise ConfigError(f"Section for '{cls.__name__}' must be a mapping.")
    known = {f.name for f in fields(cls)}
    return cls(**{key: value for key, value in data.items() if key in known})


_SECRET_KEY = re.compile(r"api[_-]?key|token|secret|passw(or)?d|credential", re.IGNORECASE)


def _reject_secrets(raw: dict[str, Any]) -> None:
    """config.yaml is for settings only. Secrets belong in .env (see arsnel/env.py)."""

    def check(mapping: dict[str, Any], where: str) -> None:
        for key in mapping:
            if _SECRET_KEY.search(str(key)):
                raise ConfigError(
                    f"'{where}{key}' looks like a secret. Keep secrets in a .env file, "
                    f"never in {CONFIG_FILENAME}."
                )

    check(raw, "")
    for name in ("organizer", "llm", "output"):
        section = raw.get(name)
        if isinstance(section, dict):
            check(section, f"{name}.")


def resolve_config_path(explicit: Path | None = None) -> Path | None:
    """Pick the config file: explicit path, $ARSNEL_CONFIG, ./config.yaml, ~/.arsnel/."""
    if explicit is not None:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ConfigError(f"Config file not found: {path}")
        return path
    env = os.environ.get(ENV_VAR)
    candidates = []
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path.cwd() / CONFIG_FILENAME)
    candidates.append(Path.home() / ".arsnel" / CONFIG_FILENAME)
    return next((p for p in candidates if p.is_file()), None)


def load_config(path: Path | None = None) -> Config:
    """Load settings, falling back to defaults for anything not specified."""
    resolved = resolve_config_path(path)
    if resolved is None:
        return Config()
    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {resolved}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{resolved} must contain a mapping at the top level.")

    _reject_secrets(raw)
    config = Config(
        organizer=_build(OrganizerConfig, raw.get("organizer")),
        llm=_build(LLMConfig, raw.get("llm")),
        output=_build(OutputConfig, raw.get("output")),
    )
    parsed_host = urlparse(config.llm.host if "://" in config.llm.host else f"http://{config.llm.host}")
    if parsed_host.username or parsed_host.password:
        raise ConfigError("llm.host must not contain a username or password. Use .env for credentials.")
    if config.output.format not in OUTPUT_FORMATS:
        allowed = ", ".join(OUTPUT_FORMATS)
        raise ConfigError(f"output.format must be one of: {allowed} (got {config.output.format!r}).")
    return config


def dump_default_config() -> str:
    """Render the default settings as YAML for `arsnel init`."""
    header = "# ARSNEL settings. Every key is optional; delete what you do not need.\n"
    return header + yaml.safe_dump(asdict(Config()), sort_keys=False, allow_unicode=True)
