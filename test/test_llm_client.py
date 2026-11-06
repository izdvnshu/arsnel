import pytest

from arsnel.llm_client import LLMClient, LLMError, LLMJSONError, extract_json, is_local_host


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Sure! Here you go:\n{"a": 1}\nHope that helps.',
    ],
)
def test_extract_json_variants(text):
    assert extract_json(text) == {"a": 1}


def test_extract_json_rejects_garbage():
    with pytest.raises(LLMJSONError):
        extract_json("no json here")


class FakeOllama:
    def __init__(self, models=None, reply="{}", error=None):
        self.models = models or []
        self.reply = reply
        self.error = error
        self.calls = []

    def list(self):
        if self.error:
            raise self.error
        return {"models": [{"model": m} for m in self.models]}

    def chat(self, **kwargs):
        if self.error:
            raise self.error
        self.calls.append(kwargs)
        return {"message": {"content": self.reply}}


def test_check_accepts_latest_tag():
    LLMClient("llama3.2", client=FakeOllama(["llama3.2:latest"])).check()


def test_check_reports_missing_model():
    with pytest.raises(LLMError, match="ollama pull llama3.2"):
        LLMClient("llama3.2", client=FakeOllama(["other:latest"])).check()


def test_check_reports_unreachable_server():
    client = LLMClient(client=FakeOllama(error=ConnectionError("refused")))
    with pytest.raises(LLMError, match="ollama serve"):
        client.check()


def test_chat_sends_system_prompt_and_options():
    fake = FakeOllama(reply=' {"ok": true} ')
    client = LLMClient("m", temperature=0.5, num_ctx=1024, client=fake)
    assert client.chat("hi", system="be brief", json_mode=True) == '{"ok": true}'
    call = fake.calls[0]
    assert call["messages"][0] == {"role": "system", "content": "be brief"}
    assert call["format"] == "json"
    assert call["options"] == {"temperature": 0.5, "num_ctx": 1024}


def test_chat_json_retries_once_then_succeeds():
    replies = iter(["not json", '{"ok": 1}'])

    class Flaky(FakeOllama):
        def chat(self, **kwargs):
            return {"message": {"content": next(replies)}}

    assert LLMClient(client=Flaky()).chat_json("q") == {"ok": 1}


@pytest.mark.parametrize(
    ("host", "local"),
    [
        ("http://localhost:11434", True),
        ("http://127.0.0.1:11434", True),
        ("http://[::1]:11434", True),
        ("localhost:11434", True),
        ("http://192.168.1.20:11434", False),
        ("https://ollama.example.com", False),
        ("http://localhost.evil.com", False),
    ],
)
def test_is_local_host(host, local):
    assert is_local_host(host) is local


def test_api_key_refused_over_plain_http_to_remote_host():
    with pytest.raises(LLMError, match="https"):
        LLMClient(host="http://192.168.1.20:11434", api_key="k")


def test_api_key_allowed_over_https_or_localhost():
    assert LLMClient(host="https://ollama.example.com", api_key="k").model == "llama3.2"
    assert LLMClient(host="http://localhost:11434", api_key="k").is_local


def test_from_config_reads_key_from_environment_only(monkeypatch):
    from arsnel.config import LLMConfig

    monkeypatch.setenv("ARSNEL_LLM_API_KEY", "from-env")
    client = LLMClient.from_config(LLMConfig(host="https://ollama.example.com"))
    assert client._api_key == "from-env"
    assert "from-env" not in repr(client)
