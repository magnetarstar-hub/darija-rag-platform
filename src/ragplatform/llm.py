from typing import Protocol

import httpx

from .config import Settings


class LLM(Protocol):
    def chat(self, messages: list[dict], json_mode: bool = False, temperature: float = 0.1) -> str: ...


class OllamaLLM:
    def __init__(self, url: str, model: str) -> None:
        self.url, self.model = url, model

    def chat(self, messages: list[dict], json_mode: bool = False, temperature: float = 0.1) -> str:
        payload = {"model": self.model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
        if json_mode:
            payload["format"] = "json"
        r = httpx.post(f"{self.url}/api/chat", json=payload, timeout=180)
        r.raise_for_status()
        return r.json()["message"]["content"]


def build_llm(s: Settings) -> LLM:
    return OllamaLLM(s.ollama_url, s.llm_model)
