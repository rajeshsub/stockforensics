"""Live Gemini client (google-genai): embeddings, streamed narrative, and grounded
JSON via the built-in google_search tool (Q17, replaces Tavily). Smoke-tested."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

from google import genai
from google.genai import types

from app.core.config import Settings


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}
        return {}


def _citations(response: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    try:
        meta = response.candidates[0].grounding_metadata
        for chunk in meta.grounding_chunks or []:
            web = getattr(chunk, "web", None)
            if web and getattr(web, "uri", None):
                out.append({"title": getattr(web, "title", "") or web.uri, "url": web.uri})
    except (AttributeError, IndexError, TypeError):
        pass
    return out


class GeminiLlmClient:
    def __init__(self, settings: Settings) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model
        self._embed_model = settings.gemini_embed_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.models.embed_content(model=self._embed_model, contents=texts)
        return [list(e.values or []) for e in (resp.embeddings or [])]

    def generate_stream(self, prompt: str) -> Iterator[str]:
        for chunk in self._client.models.generate_content_stream(
            model=self._model, contents=prompt
        ):
            if chunk.text:
                yield chunk.text

    def generate_json(self, prompt: str, *, grounded: bool = False) -> dict[str, Any]:
        if grounded:
            cfg = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        else:
            cfg = types.GenerateContentConfig(response_mime_type="application/json")
        resp = self._client.models.generate_content(model=self._model, contents=prompt, config=cfg)
        data = _extract_json(resp.text or "{}")
        data.setdefault("citations", _citations(resp))
        return data
