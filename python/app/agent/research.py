"""Agentic research helpers for the LangGraph engine (decisions #25, #28).

The loop researches the 5 LLM-EVIDENCE promoter criteria, then CODE - `assess_gaps`,
never the LLM - decides which criteria still lack solid evidence so the next pass can
target only those. `assess_gaps` gates evidence COMPLETENESS only; it sets no score and
computes no figure, so rule #10 (the deterministic/LLM boundary) stays intact."""

from __future__ import annotations

from typing import Any

from app.agent.contract import VALID_CRITERIA

# Criteria whose finding asserts a risk: a non-"none" severity claim must cite a source.
_SEVERITY_CRITERIA = {"sec_enforcement", "criminal_record", "related_party"}

# Plain-language descriptions used when re-prompting for a specific gap.
_CRITERION_DESC = {
    "ceo_tenure": "CEO tenure in years (numeric)",
    "public_co_experience": "whether the CEO has prior public-company leadership (true/false)",
    "sec_enforcement": "any SEC enforcement actions against the company or its executives",
    "criminal_record": "any criminal convictions of the company's executives",
    "related_party": "related-party transactions and their materiality",
}


def _is_sufficient(criterion: str, f: dict[str, Any]) -> bool:
    """A finding is sufficient when it carries the evidence its criterion needs."""
    if not str(f.get("finding") or "").strip():
        return False
    if criterion == "ceo_tenure":
        # A real tenure figure, not a bare True/False.
        return isinstance(f.get("value"), int | float) and not isinstance(f.get("value"), bool)
    if criterion == "public_co_experience":
        return isinstance(f.get("value"), bool)
    if criterion in _SEVERITY_CRITERIA:
        severity = str(f.get("severity", "none")).lower()
        if severity not in {"none", "low", "medium", "high"}:
            return False
        # A claimed problem (non-"none" severity) must be sourced.
        return severity == "none" or bool(f.get("source_urls"))
    return True


def assess_gaps(findings: dict[str, dict[str, Any]]) -> list[str]:
    """Return the criteria still lacking sufficient evidence (missing => gap, thin => gap)."""
    return [
        crit
        for crit in sorted(VALID_CRITERIA)
        if (f := findings.get(crit)) is None or not _is_sufficient(crit, f)
    ]


def build_targeted_prompt(
    ticker: str, context: str, gaps: list[str], name: str | None = None
) -> str:
    """Re-prompt focused only on the gap criteria, same JSON contract as `build_prompt`."""
    display = f"{name} ({ticker})" if name else ticker
    wanted = "; ".join(f"{c} ({_CRITERION_DESC.get(c, c)})" for c in gaps)
    return (
        f"You are an equity research assistant. A prior pass on {display} left THIN or "
        f"MISSING evidence for these governance criteria: {wanted}. Use a live web search "
        "(google_search) AND the SEC filing excerpts below to find SPECIFIC, sourced "
        "evidence for EACH listed criterion. Return STRICT JSON: "
        '{"narrative": str, "promoter_findings": [{"criterion": one of the listed keys, '
        '"value": number|boolean|null, "severity": "none|low|medium|high", "finding": str, '
        '"source_urls": [str]}], "citations": [{"title": str, "url": str}]}. '
        "Include one entry per listed criterion only. For ceo_tenure use value=years (number); "
        "for public_co_experience use value=true/false. Cite a source URL for any non-'none' "
        "severity. Do NOT compute any score or financial figure; report only qualitative "
        "evidence; code will threshold it.\n\n"
        f"SEC FILING EXCERPTS:\n{context or '(none)'}"
    )
