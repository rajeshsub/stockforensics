"""Live Gemini client (google-genai): embeddings, streamed narrative, and grounded
JSON via the built-in google_search tool (Q17, replaces Tavily). Smoke-tested."""

from __future__ import annotations

import concurrent.futures
import json
import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

import httpx
from google import genai
from google.genai import types

from app.core.config import Settings

# Gemini grounding returns opaque redirect URLs on this host; the real publisher
# URL (and therefore its favicon) is only reachable by following the redirect.
_REDIRECT_HOST = "vertexaisearch.cloud.google.com"


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the JSON payload out of a model response. Grounded calls can't use a
    JSON mime type, so the model returns free text that may wrap the object in
    markdown fences or prose; scan for the first brace-balanced object."""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s).strip()
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(s[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return {}


def _publisher(client: httpx.Client, url: str) -> tuple[str, str]:
    """Follow the opaque grounding redirect to the real article and return
    (final_url, publisher_domain). Header-only, short timeout; ('', '') on failure."""
    try:
        with client.stream("GET", url, follow_redirects=True, timeout=5.0) as r:
            final = str(r.url)
    except Exception:
        return "", ""
    host = (urlparse(final).hostname or "").removeprefix("www.")
    if not host or host == _REDIRECT_HOST:
        return "", ""
    return final, host


def _resolve_redirects(cites: list[dict[str, str]]) -> None:
    """Rewrite grounding-redirect citations in place to point at the real publisher
    (direct link + domain) so the UI shows the publisher's favicon, not a globe."""
    pending = [c for c in cites if _REDIRECT_HOST in c["url"]]
    if not pending:
        return
    with httpx.Client() as client, concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for c, (final, host) in zip(
            pending,
            ex.map(lambda c: _publisher(client, c["url"]), pending),
            strict=True,
        ):
            if host:
                c["url"] = final
                c["domain"] = host


def _citations(response: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    try:
        meta = response.candidates[0].grounding_metadata
        for chunk in meta.grounding_chunks or []:
            web = getattr(chunk, "web", None)
            if web and getattr(web, "uri", None):
                title = getattr(web, "title", "") or web.uri
                # Gemini grounding exposes the real publisher domain (the uri is an
                # opaque vertexaisearch redirect); keep it so the UI can show the
                # publisher's favicon instead of a generic globe.
                domain = getattr(web, "domain", "") or (title if "." in title else "")
                out.append({"title": title, "url": web.uri, "domain": domain})
    except (AttributeError, IndexError, TypeError):
        pass
    _resolve_redirects(out)
    return out


class GeminiLlmClient:
    def __init__(self, settings: Settings) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        # text-embedding-004 is only available on the stable v1 API, not v1beta
        self._embed_client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options={"api_version": "v1"},
        )
        self._model = settings.gemini_model
        self._embed_model = settings.gemini_embed_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._embed_client.models.embed_content(model=self._embed_model, contents=texts)  # type: ignore[arg-type]
        return [list(e.values or []) for e in (resp.embeddings or [])]

    def generate_stream(self, prompt: str) -> Iterator[str]:
        for chunk in self._client.models.generate_content_stream(
            model=self._model, contents=prompt
        ):
            if chunk.text:
                yield chunk.text

    def generate_text(self, prompt: str) -> str:
        resp = self._client.models.generate_content(model=self._model, contents=prompt)
        return (resp.text or "").strip()

    def generate_json_streaming(
        self, prompt: str, *, grounded: bool = False
    ) -> Iterator[tuple[str, Any]]:
        """Stream the model's *thought summaries* as it reasons, then yield the parsed
        JSON. Emits ('thought', text) chunks while thinking, then a final ('result', dict).
        thinking_config.include_thoughts surfaces Gemini's own reasoning (Q16)."""
        tools = [types.Tool(google_search=types.GoogleSearch())] if grounded else None
        cfg = types.GenerateContentConfig(
            tools=tools,
            temperature=0.0,
            thinking_config=types.ThinkingConfig(include_thoughts=True),
        )
        text_parts: list[str] = []
        grounding_resp: Any = None
        for chunk in self._client.models.generate_content_stream(
            model=self._model, contents=prompt, config=cfg
        ):
            for cand in chunk.candidates or []:
                meta = getattr(cand, "grounding_metadata", None)
                if meta and getattr(meta, "grounding_chunks", None):
                    grounding_resp = chunk
                content = getattr(cand, "content", None)
                for part in getattr(content, "parts", None) or []:
                    txt = getattr(part, "text", None)
                    if not txt:
                        continue
                    if getattr(part, "thought", False):
                        yield ("thought", txt)
                    else:
                        text_parts.append(txt)
        data = _extract_json("".join(text_parts))
        data.setdefault("citations", _citations(grounding_resp))
        yield ("result", data)

    def generate_json(self, prompt: str, *, grounded: bool = False) -> dict[str, Any]:
        if grounded:
            # temperature=0 for run-to-run determinism: the governance findings that
            # drive the Promoter score otherwise swing wildly between calls.
            cfg = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.0,
            )
        else:
            cfg = types.GenerateContentConfig(response_mime_type="application/json")
        resp = self._client.models.generate_content(model=self._model, contents=prompt, config=cfg)
        data = _extract_json(resp.text or "{}")
        data.setdefault("citations", _citations(resp))
        return data
