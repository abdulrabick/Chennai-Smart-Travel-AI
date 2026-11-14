"""Thin LLM client (Groq, OpenAI-compatible tool calling). Returns None from get_llm() when no key / package is available,
and every agent then falls back to its deterministic offline mode, so the app always works."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import settings

try:
    from dotenv import load_dotenv
    load_dotenv(settings.BASE_DIR / ".env")
except ImportError:
    pass

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")      # same model your genai/llm_service.py uses


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class GroqLLM:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        from groq import Groq
        self.client = Groq(api_key=api_key or os.environ["GROQ_API_KEY"])
        self.model = model

    def chat(self, messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.2,
             max_tokens: int = 1000) -> LLMResponse:
        kwargs = dict(model=self.model, messages=messages, temperature=temperature, max_completion_tokens=max_tokens)
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        msg = self.client.chat.completions.create(**kwargs).choices[0].message
        calls = []
        for tc in (getattr(msg, "tool_calls", None) or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(tc.id, tc.function.name, args))
        return LLMResponse((msg.content or "").strip() or None, calls)


def get_llm() -> GroqLLM | None:
    if not os.getenv("GROQ_API_KEY"):
        return None
    try:
        return GroqLLM()
    except Exception as exc:
        print(f"[llm_client] Groq unavailable: {exc}")
        return None
