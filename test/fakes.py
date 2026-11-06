"""Test doubles so no test needs ollama."""

from __future__ import annotations

from typing import Any

from arsnel.llm_client import LLMJSONError


class FakeLLM:
    """Replays queued responses from `chat_json`. An Exception instance is raised instead."""

    def __init__(self, responses: list[Any], model: str = "fake-model") -> None:
        self.responses = list(responses)
        self.model = model
        self.prompts: list[str] = []

    def chat_json(self, prompt: str, *, system: str | None = None, retries: int = 1) -> Any:
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def bad_json() -> LLMJSONError:
    return LLMJSONError("The model did not return valid JSON.")
