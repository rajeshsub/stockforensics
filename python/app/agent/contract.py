"""The agent output contract (Q5). Code consumes promoter_findings -> thresholds
into the Promoter score; narrative is display-only. This module validates/normalises
whatever the LLM returns so a malformed response degrades gracefully (Q7)."""

from __future__ import annotations

from typing import Any

VALID_CRITERIA = {
    "ceo_tenure",
    "public_co_experience",
    "sec_enforcement",
    "criminal_record",
    "related_party",
}


def validate_agent_output(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce raw LLM JSON into {narrative: str, promoter_findings: [...]}.
    Drops unknown criteria; never raises on a malformed finding."""
    narrative = str(raw.get("narrative") or "")
    findings_out: list[dict[str, Any]] = []
    for f in raw.get("promoter_findings") or []:
        if not isinstance(f, dict):
            continue
        crit = f.get("criterion")
        if crit not in VALID_CRITERIA:
            continue
        findings_out.append(
            {
                "criterion": crit,
                "value": f.get("value"),
                "severity": str(f.get("severity", "none")).lower(),
                "finding": str(f.get("finding", "")),
                "source_urls": [str(u) for u in (f.get("source_urls") or [])],
            }
        )
    return {"narrative": narrative, "promoter_findings": findings_out}
