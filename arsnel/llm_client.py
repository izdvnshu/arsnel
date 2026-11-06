"""Thin wrapper around the local ollama server, shared by resume and notes."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlparse

from arsnel.config import LLMConfig


API_KEY_ENV = "ARSNEL_LLM_API_KEY"  # optional; set it in .env, never in config.yaml


class LLMError(RuntimeError):
    """Anything that goes wrong talking to the local model."""


class LLMJSONError(LLMError):
    """The model answered, but not with parseable JSON."""


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> Any:
    """Parse JSON from model output, tolerating code fences and surrounding prose."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMJSONError("The model did not return valid JSON.")


def is_local_host(host: str) -> bool:
    """True if `host` points at this machine (so no text leaves the computer)."""
    parsed = urlparse(host if "://" in host else f"http://{host}")
    return (parsed.hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}


def _model_names(listing: Any) -> list[str]:
    try:
        models = listing["models"]
    except (KeyError, TypeError):
        return []
    names = []
    for entry in models:
        name = entry.get("model") or entry.get("name")
        if name:
            names.append(str(name))
    return names


class LLMClient:
    """All model calls go through here so modules never touch ollama directly."""

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
        temperature: float = 0.2,
        num_ctx: int = 8192,
        *,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.host = host
        self.temperature = temperature
        self.num_ctx = num_ctx
        self._api_key = api_key or None  # never printed, logged or written anywhere
        self._client = client
        if self._api_key and not self.is_local and not host.lower().startswith("https://"):
            raise LLMError(
                "Refusing to send an API key over plain http to a remote host. "
                "Use an https:// llm.host."
            )

    @classmethod
    def from_config(cls, cfg: LLMConfig, model: str | None = None) -> LLMClient:
        return cls(
            model=model or cfg.model,
            host=cfg.host,
            temperature=cfg.temperature,
            num_ctx=cfg.num_ctx,
            api_key=os.environ.get(API_KEY_ENV),
        )

    @property
    def is_local(self) -> bool:
        return is_local_host(self.host)

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import ollama
            except ImportError as exc:  # pragma: no cover - dependency is declared
                raise LLMError("The 'ollama' package is missing. Run: pip install ollama") from exc
            kwargs: dict[str, Any] = {}
            if self._api_key:
                kwargs["headers"] = {"Authorization": f"Bearer {self._api_key}"}
            self._client = ollama.Client(host=self.host, **kwargs)
        return self._client

    def check(self) -> None:
        """Fail early, with an actionable message, if ollama or the model is unavailable."""
        try:
            listing = self.client.list()
        except LLMError:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc
        names = _model_names(listing)
        has_model = self.model in names or (":" not in self.model and f"{self.model}:latest" in names)
        if not has_model:
            raise LLMError(f"Model '{self.model}' is not installed. Run: ollama pull {self.model}")

    def chat(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }
        if json_mode:
            kwargs["format"] = "json"
        try:
            response = self.client.chat(**kwargs)
        except LLMError:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc
        return str(response["message"]["content"]).strip()

    def chat_json(self, prompt: str, *, system: str | None = None, retries: int = 1) -> Any:
        """Ask for JSON and parse it, retrying once with a stricter reminder."""
        last_error: LLMError | None = None
        for attempt in range(retries + 1):
            suffix = "" if attempt == 0 else "\n\nReturn ONLY valid JSON. No commentary."
            text = self.chat(prompt + suffix, system=system, json_mode=True)
            try:
                return extract_json(text)
            except LLMJSONError as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    def _translate(self, exc: Exception) -> LLMError:
        status = getattr(exc, "status_code", None)
        if status == 404:
            return LLMError(f"Model '{self.model}' is not installed. Run: ollama pull {self.model}")
        text = str(exc).lower()
        if isinstance(exc, ConnectionError) or "connect" in text or "refused" in text:
            return LLMError(
                f"Cannot reach ollama at {self.host}. Start it with `ollama serve` "
                "(or open the Ollama app) and try again."
            )
        return LLMError(f"ollama request failed: {exc}")
