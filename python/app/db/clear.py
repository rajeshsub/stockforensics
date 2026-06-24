"""Wipe every cache so the next run refetches and re-evaluates from scratch:
all SQLite rows (scores, pipeline runs, LLM + embedding caches) and every Pinecone
namespace (the embedded filing chunks used for AI eval). Run via `make clear`.

The DB schema and Pinecone index are kept; only their contents are cleared."""

from __future__ import annotations

from sqlalchemy import delete

from app.core.config import get_settings
from app.db.engine import session_scope
from app.db.models import CompanyScore, EmbeddingCache, LlmCache, PipelineRun

_TABLES = (CompanyScore, PipelineRun, LlmCache, EmbeddingCache)


def clear_sqlite() -> None:
    with session_scope() as s:
        for model in _TABLES:
            n = s.execute(delete(model)).rowcount
            print(f"sqlite: cleared {model.__tablename__} ({n} rows)")


def clear_pinecone() -> None:
    settings = get_settings()
    if not settings.pinecone_api_key:
        print("pinecone: no API key set, skipping")
        return
    from pinecone import Pinecone

    pc = Pinecone(api_key=settings.pinecone_api_key)
    if settings.pinecone_index not in {i["name"] for i in pc.list_indexes()}:
        print(f"pinecone: index '{settings.pinecone_index}' does not exist, nothing to clear")
        return
    idx = pc.Index(settings.pinecone_index)
    try:
        namespaces = list((idx.describe_index_stats().get("namespaces") or {}).keys())
    except Exception as e:  # network/transient
        print(f"pinecone: could not list namespaces ({type(e).__name__}: {e})")
        return
    if not namespaces:
        print("pinecone: no namespaces to clear")
        return
    for ns in namespaces:
        try:
            idx.delete(delete_all=True, namespace=ns)
            print(f"pinecone: cleared namespace '{ns}'")
        except Exception as e:
            print(f"pinecone: namespace '{ns}' skipped ({type(e).__name__}: {e})")


def main() -> None:
    clear_sqlite()
    clear_pinecone()
    print("clear complete.")


if __name__ == "__main__":
    main()
