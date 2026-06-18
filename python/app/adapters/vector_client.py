"""Live Pinecone vector store (serverless). Index lazy-created on first use
(cloud; not offline-bootstrappable). Namespace per ticker. Smoke-tested."""

from __future__ import annotations

from typing import Any

from pinecone import Pinecone, ServerlessSpec

from app.adapters.protocols import VectorItem, VectorMatch
from app.core.config import Settings

EMBED_DIM = 768  # Gemini text-embedding-004


class PineconeVectorClient:
    def __init__(self, settings: Settings, dim: int = EMBED_DIM) -> None:
        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self._name = settings.pinecone_index
        self._cloud = settings.pinecone_cloud
        self._region = settings.pinecone_region
        self._dim = dim
        self._index: Any = None

    def _idx(self) -> Any:
        if self._index is None:
            existing = {i["name"] for i in self._pc.list_indexes()}
            if self._name not in existing:
                self._pc.create_index(
                    name=self._name,
                    dimension=self._dim,
                    metric="cosine",
                    spec=ServerlessSpec(cloud=self._cloud, region=self._region),
                )
            self._index = self._pc.Index(self._name)
        return self._index

    def upsert(self, namespace: str, items: list[VectorItem]) -> None:
        self._idx().upsert(
            vectors=[(it.id, it.values, it.metadata) for it in items],
            namespace=namespace,
        )

    def query(self, namespace: str, vector: list[float], top_k: int = 5) -> list[VectorMatch]:
        res = self._idx().query(
            vector=vector, top_k=top_k, namespace=namespace, include_metadata=True
        )
        return [
            VectorMatch(m["id"], m["score"], dict(m.get("metadata") or {}))
            for m in res.get("matches", [])
        ]
