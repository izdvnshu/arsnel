import os
import re
from pathlib import Path

from arsnel.env import has_loose_permissions, load_dotenv, parse_env

ROOT = Path(__file__).resolve().parent.parent


def test_parse_env_handles_comments_quotes_and_export():
    text = "\n".join(
        [
            "# comment",
            "",
            "PLAIN=value",
            'QUOTED="has spaces # not a comment"',
            "SINGLE='x'",
            "export EXPORTED=1",
            "TRAILING=abc # comment",
            "not a pair",
            "1BAD=nope",
        ]
    )
    assert parse_env(text) == {
        "PLAIN": "value",
        "QUOTED": "has spaces # not a comment",
        "SINGLE": "x",
        "EXPORTED": "1",
        "TRAILING": "abc",
    }


def test_load_dotenv_does_not_override_real_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ARSNEL_TEST_A=from_file\nARSNEL_TEST_B=from_file\n", encoding="utf-8")
    monkeypatch.setenv("ARSNEL_TEST_A", "from_shell")
    monkeypatch.delenv("ARSNEL_TEST_B", raising=False)
    assert load_dotenv(env_file) == env_file
    assert os.environ["ARSNEL_TEST_A"] == "from_shell"
    assert os.environ["ARSNEL_TEST_B"] == "from_file"
    os.environ.pop("ARSNEL_TEST_B", None)


def test_load_dotenv_returns_none_when_missing(tmp_path):
    assert load_dotenv(tmp_path / "nope.env") is None


def test_permission_check(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("A=1")
    if os.name == "nt":
        assert has_loose_permissions(env_file) is False
        return
    env_file.chmod(0o600)
    assert has_loose_permissions(env_file) is False
    env_file.chmod(0o644)
    assert has_loose_permissions(env_file) is True


def test_gitignore_blocks_env_but_keeps_example():
    lines = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in lines and "!.env.example" in lines and "config.yaml" in lines


def test_no_hardcoded_secrets_in_source():
    pattern = re.compile(r"(api[_-]?key|token|secret|passw(or)?d)\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE)
    for path in (ROOT / "arsnel").rglob("*.py"):
        assert not pattern.search(path.read_text(encoding="utf-8")), f"possible secret in {path}"
