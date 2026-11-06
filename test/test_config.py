from pathlib import Path

import pytest
import yaml

from arsnel.config import Config, ConfigError, dump_default_config, load_config

ROOT = Path(__file__).resolve().parent.parent


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("ARSNEL_CONFIG", raising=False)
    assert load_config() == Config()


def test_partial_file_merges_with_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("llm:\n  model: qwen2.5:3b\nunknown_key: 1\n", encoding="utf-8")
    config = load_config(path)
    assert config.llm.model == "qwen2.5:3b"
    assert config.llm.host == Config().llm.host
    assert config.organizer == Config().organizer


def test_missing_explicit_path_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")


def test_invalid_yaml_and_bad_format_raise(tmp_path):
    broken = tmp_path / "broken.yaml"
    broken.write_text("llm: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(broken)
    bad = tmp_path / "bad.yaml"
    bad.write_text("output:\n  format: pdf\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="output.format"):
        load_config(bad)


def test_env_var_is_used(tmp_path, monkeypatch):
    path = tmp_path / "custom.yaml"
    path.write_text("llm:\n  model: tiny\n", encoding="utf-8")
    monkeypatch.setenv("ARSNEL_CONFIG", str(path))
    assert load_config().llm.model == "tiny"


def test_tilde_is_expanded():
    assert "~" not in str(Config().organizer.watch_path)
    assert Config().organizer.watch_path.name == "Downloads"


def test_example_file_matches_defaults():
    """config.example.yaml must stay in sync with the code defaults."""
    example = yaml.safe_load((ROOT / "config.example.yaml").read_text(encoding="utf-8"))
    assert load_config(ROOT / "config.example.yaml") == Config()
    assert set(example) == {"organizer", "llm", "output"}


def test_init_template_round_trips(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(dump_default_config(), encoding="utf-8")
    assert load_config(path) == Config()


@pytest.mark.parametrize(
    "yaml_text",
    [
        "llm:\n  api_key: abc\n",
        "llm:\n  token: abc\n",
        "organizer:\n  password: x\n",
        "secret: x\n",
    ],
)
def test_secrets_in_config_are_rejected(tmp_path, yaml_text):
    path = tmp_path / "config.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(ConfigError, match=".env"):
        load_config(path)


def test_credentials_in_host_url_are_rejected(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("llm:\n  host: https://user:pass@example.com\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="username or password"):
        load_config(path)
