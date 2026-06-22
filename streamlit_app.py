"""StockForensics Streamlit dashboard.

Fintech Light theme. API key gates all content. No sidebar. No leaderboard.
Deterministic scoring imported directly; no HTTP layer.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_python_dir = Path(__file__).parent / "python"
if str(_python_dir) not in sys.path:
    sys.path.insert(0, str(_python_dir))

import streamlit as st  # noqa: E402

# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------

_GOOD = "#10b981"
_FAIR = "#f59e0b"
_BAD = "#ef4444"
_ACCENT = "#2563eb"

_CSS = """
<style>
section[data-testid="stSidebar"] { display: none !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { display: none; }

.block-container {
    max-width: 960px !important;
    padding-top: 0.5rem !important;
    padding-bottom: 3rem !important;
}

/* Score card grid */
.sf-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-bottom: 18px;
}
.sf-card {
    background: #ffffff;
    border: 1px solid #e6ebf2;
    border-radius: 12px;
    padding: 16px 18px;
    box-shadow: 0 1px 3px rgba(20,30,50,.05);
}
.sf-card-label {
    color: #7b8798; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .4px;
}
.sf-card-score {
    font-size: 34px; font-weight: 800; margin: 8px 0 2px;
    font-variant-numeric: tabular-nums; color: #1e2733;
}
.sf-card-den { color: #7b8798; font-size: 17px; font-weight: 400; }
.sf-bar { height: 7px; border-radius: 999px; background: #eef2f7;
          overflow: hidden; margin-top: 10px; }
.sf-bar > i { display: block; height: 100%; border-radius: 999px; }
.sf-card-meta { display: flex; justify-content: space-between;
                margin-top: 8px; color: #7b8798; font-size: 12px; }
.sf-card-composite {
    display: flex; flex-direction: column; justify-content: center;
    align-items: center;
    background: linear-gradient(135deg, #2563eb, #0ea5e9) !important;
    border: none !important;
}

/* Generic panel */
.sf-panel {
    background: #ffffff;
    border: 1px solid #e6ebf2;
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 18px;
    box-shadow: 0 1px 3px rgba(20,30,50,.05);
}
.sf-panel-title {
    color: #7b8798; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .4px; margin: 0 0 14px 0;
}

/* Breakdown table */
.sf-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.sf-table th { color: #7b8798; font-size: 11px; font-weight: 600;
               text-transform: uppercase; padding: 8px 6px;
               border-bottom: 1px solid #e6ebf2; text-align: left; }
.sf-table td { padding: 9px 6px; border-bottom: 1px solid #e6ebf2; color: #1e2733; }
.sf-table td.r { text-align: right; }
.sf-table th.r { text-align: right; }
.sf-ok { color: #10b981; font-weight: 700; }
.sf-no { color: #ef4444; font-weight: 700; }
.sf-na { color: #7b8798; }
.sf-tag { font-size: 10px; padding: 2px 6px; border-radius: 999px;
          background: #eef2ff; color: #2563eb; font-weight: 700; }
.sf-tag-llm { background: #fff1e6; color: #c2620e; }

/* Thinking stream stages */
.sf-stage { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 10px; }
.sf-stage-icon {
    flex-shrink: 0; width: 20px; height: 20px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 700; color: #fff;
}
.sf-stage-icon.done { background: #10b981; }
.sf-stage-icon.running { background: #2563eb; }
.sf-stage-icon.error { background: #ef4444; }
.sf-stage-text { color: #7b8798; font-size: 12px; line-height: 1.5; }
.sf-stage-text strong { color: #1e2733; }

/* Company header chips */
.sf-chip {
    display: inline-block; font-size: 12px; color: #7b8798;
    background: #f5f7fb; border: 1px solid #e6ebf2;
    padding: 3px 10px; border-radius: 999px; margin-right: 6px;
}
.sf-chip-accent { background: #2563eb; color: #fff; border-color: #2563eb; }

/* Locked state */
.sf-locked {
    background: #f5f7fb; border: 1px dashed #d1d9e6;
    border-radius: 12px; padding: 48px 24px; text-align: center;
    color: #7b8798; margin-bottom: 18px;
}
.sf-locked strong { color: #1e2733; display: block; font-size: 16px; margin-bottom: 6px; }

/* How to use */
.sf-howto {
    background: #fffbeb; border: 1px solid #fcd34d;
    border-radius: 12px; padding: 16px 20px; margin-top: 28px;
}
.sf-howto h4 { color: #78350f; font-size: 13px; font-weight: 700; margin: 0 0 10px; }
.sf-howto ol { margin: 0; padding-left: 18px; color: #92400e; font-size: 13px; line-height: 1.9; }
.sf-howto strong { color: #b45309; }

/* Step badges */
.sf-step { display: inline-block; background: #ef4444; color: #fff;
           font-size: 10px; font-weight: 700; padding: 2px 5px;
           border-radius: 3px; margin-right: 4px; }
.sf-step-2 { background: #2563eb; }

/* Emphasise the ticker selectbox */
div[data-testid="stSelectbox"] label { font-weight: 700 !important; }
div[data-testid="stSelectbox"] > div > div {
    border: 2px solid #2563eb !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}
</style>
"""

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _score_color(pct: float) -> str:
    if pct >= 75:
        return _GOOD
    return _FAIR if pct >= 50 else _BAD


def _score_label(pct: float) -> str:
    if pct >= 75:
        return "strong"
    return "fair" if pct >= 50 else "weak"


def _fmt_cap(cap: float | None) -> str:
    if cap is None:
        return "n/a"
    if cap >= 1e12:
        return f"${cap / 1e12:.2f}T"
    if cap >= 1e9:
        return f"${cap / 1e9:.1f}B"
    return f"${cap / 1e6:.0f}M"


def _is_stale(detail: dict[str, Any]) -> bool:
    run_date = detail.get("run_date")
    if run_date is None:
        return True
    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=UTC)
    return (datetime.now(UTC) - run_date) > timedelta(hours=3)


def _parse_sse(stream: Any) -> Any:
    """Yield (event_type, data_dict) pairs from an analyze_stream iterator."""
    event_type = ""
    for chunk in stream:
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                try:
                    yield event_type, json.loads(line[6:])
                except json.JSONDecodeError:
                    pass


# ---------------------------------------------------------------------------
# Cached resources (run once per server process)
# ---------------------------------------------------------------------------


def _inject_hf_secrets() -> None:
    """Pull Hugging Face Space secrets into env for pydantic-settings."""
    try:
        for key in ("GEMINI_API_KEY", "PINECONE_API_KEY", "SEC_USER_AGENT"):
            val = st.secrets.get(key, "")
            if val:
                os.environ.setdefault(key, val)
    except Exception:
        pass


@st.cache_resource
def _boot_db() -> None:
    """Migrate + seed the DB exactly once per Streamlit server process."""
    from sqlalchemy import func, select

    from app.core.config import get_settings
    from app.core.logging import configure_logging
    from app.db.engine import session_scope
    from app.db.migrate import migrate
    from app.db.models import CompanyScore

    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    try:
        migrate()
    except Exception:
        pass
    with session_scope() as sess:
        count = sess.execute(select(func.count(CompanyScore.id))).scalar()
    if not count:
        from app.db.seed import seed

        if s.has("gemini_api_key"):
            try:
                n = seed(force_fixtures=False)
            except Exception:
                n = 0
            if not n:
                seed(force_fixtures=True)
        else:
            seed(force_fixtures=True)


@st.cache_resource
def _get_adapters() -> Any:
    from app.core.clients import build_adapters
    from app.core.config import get_settings

    s = get_settings()
    force = not (s.has("gemini_api_key") and s.has("pinecone_api_key"))
    return build_adapters(s, force_fixtures=force)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _key_valid(entered: str) -> bool:
    """True when entered key matches API_KEY setting.
    If API_KEY is not configured, any non-empty string is accepted (dev mode).
    """
    from app.core.config import get_settings

    configured = get_settings().api_key
    if not configured:
        return bool(entered)
    return entered == configured


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------


def _load_companies() -> list[dict[str, Any]]:
    from app.db.engine import session_scope
    from app.db.repository import list_companies

    with session_scope() as sess:
        rows = list_companies(sess)
    return [
        {
            "ticker": c.ticker,
            "display": f"{c.name} ({c.ticker})" if c.name else c.ticker,
            "name": c.name or c.ticker,
            "sector": c.sector or "n/a",
            "market_cap": c.market_cap,
        }
        for c in rows
    ]


def _load_detail(ticker: str) -> dict[str, Any] | None:
    from app.db.engine import session_scope
    from app.db.repository import get_company

    with session_scope() as sess:
        c = get_company(sess, ticker.upper())
        if c is None:
            return None
        avail = [
            v["normalized_pct"] for v in c.scores.values() if v.get("max_score", 0) > 0
        ]
        full_composite = round(sum(avail) / len(avail), 1) if avail else 0.0
        return {
            "ticker": c.ticker,
            "name": c.name or c.ticker,
            "sector": c.sector or "n/a",
            "market_cap": c.market_cap,
            "composite_pct_4dim": c.composite_pct or 0.0,
            "composite_pct_full": full_composite,
            "promoter_live": c.promoter_live,
            "scores": c.scores,
            "narrative": c.narrative or "",
            "composite_narrative": c.composite_narrative or "",
            "citations": c.citations or [],
            "thinking": c.thinking or [],
            "reasoning": c.reasoning or "",
            "run_date": c.run_date,
        }


# ---------------------------------------------------------------------------
# UI renderers
# ---------------------------------------------------------------------------


def _render_score_cards(detail: dict[str, Any]) -> None:
    scores = detail["scores"]
    dim_order = [
        ("graham", "Graham"),
        ("buffett", "Buffett Quality"),
        ("munger", "Munger Composite"),
        ("earnings_quality", "Earnings Quality"),
        ("promoter_integrity", "Promoter Integrity"),
    ]
    cards = ""
    for key, label in dim_order:
        d = scores.get(key, {})
        pct = d.get("normalized_pct", 0)
        score = d.get("score", 0)
        max_s = d.get("max_score", 0) or d.get("nominal_max", 10)
        conf = d.get("confidence", 0)
        color = _score_color(pct)
        lbl = _score_label(pct)
        if key == "promoter_integrity" and not detail["promoter_live"]:
            cards += (
                f'<div class="sf-card">'
                f'<div class="sf-card-label">{label}</div>'
                f'<div class="sf-card-score" style="color:#7b8798;font-size:18px;margin-top:12px">Run AI to score</div>'
                f'<div class="sf-bar"><i style="width:0%"></i></div>'
                f'<div class="sf-card-meta"><span>live AI only</span></div>'
                f"</div>"
            )
        else:
            cards += (
                f'<div class="sf-card">'
                f'<div class="sf-card-label">{label}</div>'
                f'<div class="sf-card-score">{score:.1f}<span class="sf-card-den">/{max_s:.0f}</span></div>'
                f'<div class="sf-bar"><i style="width:{pct:.0f}%;background:{color}"></i></div>'
                f'<div class="sf-card-meta"><span>{pct:.0f}% &middot; {lbl}</span><span>conf {conf:.2f}</span></div>'
                f"</div>"
            )
    composite = detail["composite_pct_full"]
    cards += (
        f'<div class="sf-card sf-card-composite">'
        f'<div class="sf-card-label" style="color:#dbeafe">Composite (5-dim)</div>'
        f'<div class="sf-card-score" style="color:#fff;font-size:42px">{composite:.0f}'
        f'<span class="sf-card-den" style="color:#dbeafe">%</span></div>'
        f'<div class="sf-card-meta" style="color:#dbeafe;justify-content:center">avg of all dimensions</div>'
        f"</div>"
    )
    st.markdown(f'<div class="sf-grid">{cards}</div>', unsafe_allow_html=True)


def _render_radar(detail: dict[str, Any]) -> None:
    import plotly.graph_objects as go

    scores = detail["scores"]
    dims = [
        ("graham", "Graham"),
        ("buffett", "Buffett"),
        ("munger", "Munger"),
        ("earnings_quality", "Earnings"),
        ("promoter_integrity", "Promoter"),
    ]
    vals = [scores.get(k, {}).get("normalized_pct", 0) for k, _ in dims]
    labels = [lbl for _, lbl in dims]

    fig = go.Figure(
        go.Scatterpolar(
            r=vals + [vals[0]],
            theta=labels + [labels[0]],
            fill="toself",
            fillcolor="rgba(37,99,235,0.12)",
            line=dict(color="#2563eb", width=2),
        )
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=9),
                gridcolor="#e6ebf2",
            ),
            angularaxis=dict(tickfont=dict(size=11, color="#7b8798")),
            bgcolor="#f9fafb",
        ),
        showlegend=False,
        margin=dict(l=30, r=30, t=20, b=20),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_breakdown(detail: dict[str, Any], dim_key: str) -> None:
    dim_data = detail["scores"].get(dim_key, {})
    breakdown = dim_data.get("breakdown", [])
    if not breakdown:
        st.caption("No breakdown data available.")
        return
    score = dim_data.get("score", 0)
    max_s = dim_data.get("max_score", 0)
    rows = ""
    for c in breakdown:
        prov = c.get("provenance", "CODE")
        tag_cls = "sf-tag-llm" if prov == "LLM-EVIDENCE" else "sf-tag"
        tag_lbl = "LLM" if prov == "LLM-EVIDENCE" else "CODE"
        status = c.get("status", "NA")
        if status == "PASS":
            sym_cell = '<td style="color:#10b981;font-size:16px;font-weight:700;text-align:center">&#10003;</td>'
        elif status == "FAIL":
            sym_cell = '<td style="color:#ef4444;font-size:16px;font-weight:700;text-align:center">&#10007;</td>'
        else:
            sym_cell = '<td style="color:#7b8798;text-align:center">-</td>'
        raw = c.get("value")
        pts = c.get("earned", 0)
        rows += (
            f"<tr>"
            f"<td>{c.get('criterion','')}</td>"
            f'<td><span class="{tag_cls}">{tag_lbl}</span></td>'
            f'<td class="r">{raw if raw is not None else "n/a"}</td>'
            f"{sym_cell}"
            f'<td class="r">{pts:.2f}</td>'
            f"</tr>"
        )
    st.markdown(
        f'<div class="sf-panel">'
        f'<div class="sf-panel-title">Breakdown &middot; {score:.1f} / {max_s:.1f}</div>'
        f'<table class="sf-table">'
        f"<tr><th>Criterion</th><th>Source</th><th class='r'>Value</th><th style='text-align:center'>Status</th><th class='r'>Pts</th></tr>"
        f"{rows}"
        f"</table></div>",
        unsafe_allow_html=True,
    )


def _run_analysis_stream(ticker: str) -> None:
    """Stream AI analysis, updating a scrollable panel as events arrive."""
    from app.pipeline.analyze import analyze_stream

    st.markdown(
        '<div class="sf-panel-title" style="margin-bottom:10px">Live Analysis Stream</div>',
        unsafe_allow_html=True,
    )
    stream_box = st.container(height=280)
    placeholder = stream_box.empty()
    stages_html = ""

    def _update(extra: str) -> None:
        nonlocal stages_html
        stages_html += extra
        placeholder.markdown(stages_html, unsafe_allow_html=True)

    citations: list[dict[str, Any]] = []

    for event_type, data in _parse_sse(analyze_stream(_get_adapters(), ticker)):
        if event_type == "stage":
            _update(
                f'<div class="sf-stage">'
                f'<div class="sf-stage-icon done">&#10003;</div>'
                f'<div class="sf-stage-text"><strong>{data.get("stage","")}</strong>'
                f"<br>{data.get('message','')}</div></div>"
            )
        elif event_type == "thought":
            _update(
                f'<div class="sf-stage">'
                f'<div class="sf-stage-icon running">&#9679;</div>'
                f'<div class="sf-stage-text">{data.get("text","")}</div></div>'
            )
        elif event_type == "citation":
            citations.append(data)
        elif event_type == "error":
            _update(
                f'<div class="sf-stage">'
                f'<div class="sf-stage-icon error">!</div>'
                f'<div class="sf-stage-text" style="color:#ef4444">{data.get("message","error")}</div></div>'
            )

    if citations:
        st.session_state["citations"] = citations
    st.rerun()


def _render_narratives(detail: dict[str, Any]) -> None:
    if detail["narrative"]:
        st.markdown(
            f'<div class="sf-panel">'
            f'<div class="sf-panel-title">Qualitative Narrative</div>'
            f'<div style="font-size:14px;line-height:1.75;color:#1e2733">{detail["narrative"]}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    if detail["composite_narrative"]:
        st.markdown(
            f'<div class="sf-panel">'
            f'<div class="sf-panel-title">AI Composite Analysis</div>'
            f'<div style="font-size:14px;line-height:1.75;color:#1e2733">{detail["composite_narrative"]}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    cites = detail.get("citations") or st.session_state.get("citations", [])
    if cites:
        links = " &nbsp;&middot;&nbsp; ".join(
            f'<a href="{c.get("url","#")}" target="_blank" style="color:#2563eb;font-size:12px">'
            f'{c.get("title","Source")}</a>'
            for c in cites
        )
        st.markdown(
            f'<div style="margin:-12px 0 18px;color:#7b8798;font-size:12px">Sources: {links}</div>',
            unsafe_allow_html=True,
        )


def _render_thinking_replay(detail: dict[str, Any]) -> None:
    """Replay cached AI thinking stages and reasoning from DB."""
    thinking = detail.get("thinking") or []
    reasoning = detail.get("reasoning") or ""
    run_date = detail.get("run_date")

    label = "AI Analysis"
    if run_date is not None:
        ts = (
            run_date.strftime("%Y-%m-%d %H:%M UTC")
            if run_date.tzinfo
            else run_date.strftime("%Y-%m-%d %H:%M")
        )
        label += f" &middot; cached {ts}"

    st.markdown(
        f'<div class="sf-panel-title" style="margin-bottom:10px">{label}</div>',
        unsafe_allow_html=True,
    )
    stream_box = st.container(height=280)
    html = ""
    for s in thinking:
        html += (
            f'<div class="sf-stage">'
            f'<div class="sf-stage-icon done">&#10003;</div>'
            f'<div class="sf-stage-text"><strong>{s.get("stage","")}</strong>'
            f'<br>{s.get("message","")}</div></div>'
        )
    if reasoning:
        html += (
            f'<div class="sf-stage">'
            f'<div class="sf-stage-icon running">&#9679;</div>'
            f'<div class="sf-stage-text" style="white-space:pre-wrap">{reasoning}</div></div>'
        )
    if html:
        stream_box.markdown(html, unsafe_allow_html=True)
    else:
        stream_box.caption("No thinking steps recorded.")


def _render_weight_editor(detail: dict[str, Any]) -> None:
    with st.expander("Weight Editor - adjust dimension importance for composite score"):
        st.caption(
            "Set a dimension weight to zero to exclude it from the composite. "
            "Weights renormalise automatically across all non-zero dimensions. "
            "Individual dimension scores are unchanged; only the composite changes."
        )
        col1, col2 = st.columns(2)
        scores = detail["scores"]
        dim_specs = [
            ("graham", "Graham"),
            ("buffett", "Buffett Quality"),
            ("munger", "Munger Composite"),
            ("earnings_quality", "Earnings Quality"),
            ("promoter_integrity", "Promoter Integrity"),
        ]
        dim_weights: dict[str, float] = {}
        for i, (key, label) in enumerate(dim_specs):
            col = col1 if i % 2 == 0 else col2
            with col:
                dim_weights[key] = st.slider(label, 0.0, 2.0, 1.0, 0.1, key=f"w_{key}")

        total_w = sum(dim_weights.values())
        if total_w > 0:
            weighted = (
                sum(
                    scores.get(k, {}).get("normalized_pct", 0) * w
                    for k, w in dim_weights.items()
                )
                / total_w
            )
            st.success(f"Weighted Composite: {weighted:.1f}%")
        else:
            st.warning("All weights are zero - nothing to compute.")


def _render_how_to_use() -> None:
    st.markdown(
        '<div class="sf-howto">'
        "<h4>How to Use StockForensics</h4>"
        "<ol>"
        "<li><strong>Step 1 - Enter API Key:</strong> Paste your API key in the field at the top right. This authorizes your session.</li>"
        "<li><strong>Step 2 - Pick a Stock:</strong> Choose any company from the dropdown. Switch stocks at any time; results load automatically.</li>"
        "</ol>"
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="StockForensics",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    _inject_hf_secrets()
    _boot_db()

    # --- Top bar: logo + disclaimer + STEP 1 API key ---
    col_logo, col_key = st.columns([3, 2])
    with col_logo:
        st.markdown(
            '<div style="padding:10px 0 6px">'
            '<span style="font-weight:800;color:#2563eb;font-size:16px">&#9675; StockForensics</span>'
            '&nbsp;&nbsp;<span style="color:#7b8798;font-size:11px">Educational research &middot; not investment advice</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    with col_key:
        if not st.session_state.get("authenticated"):
            st.markdown(
                '<p style="margin:0 0 2px;font-size:11px;color:#7b8798">'
                '<span class="sf-step">STEP 1</span> API Key</p>',
                unsafe_allow_html=True,
            )
            with st.form("api_key_form", clear_on_submit=False):
                entered_key = st.text_input(
                    "API Key",
                    type="password",
                    placeholder="Paste API key then click Unlock",
                    label_visibility="collapsed",
                )
                submitted = st.form_submit_button(
                    "Unlock", use_container_width=True, type="primary"
                )
                if submitted:
                    if _key_valid(entered_key):
                        st.session_state["authenticated"] = True
                        st.rerun()
                    else:
                        st.error("Invalid API key.")
        else:
            st.markdown(
                '<div style="padding:10px 0 6px;text-align:right">'
                '<span style="color:#10b981;font-size:12px;font-weight:700">&#10003; Authorized</span>'
                "</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        '<hr style="border:none;border-top:1px solid #e6ebf2;margin:6px 0 18px"/>',
        unsafe_allow_html=True,
    )

    if not st.session_state.get("authenticated"):
        st.markdown(
            '<div class="sf-locked">'
            "<strong>Enter your API key above to continue</strong>"
            "Paste the key provided by the app owner in the field at the top right, then click Unlock."
            "</div>",
            unsafe_allow_html=True,
        )
        _render_how_to_use()
        return

    # --- STEP 2: Ticker selector ---
    companies = _load_companies()
    if not companies:
        st.error("No companies in database. Run the batch pipeline first.")
        return

    ticker_map = {c["display"]: c["ticker"] for c in companies}
    displays = list(ticker_map.keys())

    st.markdown(
        '<p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#1e2733">'
        '<span class="sf-step sf-step-2">STEP 2</span> Pick a stock to analyze:</p>',
        unsafe_allow_html=True,
    )
    selected_display = st.selectbox(
        "Pick a stock",
        displays,
        index=None,
        placeholder="Select a stock to analyze...",
        label_visibility="collapsed",
        key="ticker_select",
    )

    if selected_display is None:
        st.markdown(
            '<div class="sf-locked">'
            "<strong>Select a stock above to get started</strong>"
            "Choose a company from the dropdown to view its StockForensics analysis."
            "</div>",
            unsafe_allow_html=True,
        )
        _render_how_to_use()
        return

    ticker = ticker_map[selected_display]

    # Clear stale citation cache when ticker changes
    if st.session_state.get("_last_ticker") != ticker:
        st.session_state.pop("citations", None)
        st.session_state["_last_ticker"] = ticker

    detail = _load_detail(ticker)
    if detail is None:
        st.error(f"No data found for {ticker}.")
        return

    # Company header
    st.markdown(
        f'<div style="margin:18px 0">'
        f'<div style="font-size:26px;font-weight:700;color:#1e2733;margin-bottom:6px">{detail["name"]}</div>'
        f'<span class="sf-chip sf-chip-accent">{detail["ticker"]}</span>'
        f'<span class="sf-chip">{detail["sector"]}</span>'
        f'<span class="sf-chip">{_fmt_cap(detail["market_cap"])} mkt cap</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    # Score cards (3-col grid)
    _render_score_cards(detail)

    # Radar + dimension breakdown side by side
    col_radar, col_table = st.columns([1, 1.35])
    with col_radar:
        with st.container(border=True):
            st.markdown(
                '<div class="sf-panel-title" style="margin-bottom:0">Radar &middot; 5 dimensions</div>',
                unsafe_allow_html=True,
            )
            _render_radar(detail)
    with col_table:
        dim_labels = {
            "graham": "Graham",
            "buffett": "Buffett",
            "munger": "Munger",
            "earnings_quality": "Earnings",
            "promoter_integrity": "Promoter",
        }
        chosen_dim = st.radio(
            "View breakdown for:",
            list(dim_labels.keys()),
            format_func=lambda k: dim_labels[k],
            horizontal=True,
            key="breakdown_dim",
        )
        _render_breakdown(detail, chosen_dim)

    # AI analysis: auto-run if no cached result; show cache if fresh; re-run only if stale
    has_result = bool(detail["narrative"] or detail["promoter_live"])
    stale = _is_stale(detail)
    if has_result:
        _render_narratives(detail)
        with st.container(border=True):
            _render_thinking_replay(detail)
        if stale:
            if st.button(
                "Re-run AI Analysis",
                type="secondary",
                help="Data is older than 3 hours",
            ):
                _run_analysis_stream(ticker)
    else:
        with st.container(border=True):
            st.markdown(
                '<div class="sf-panel-title" style="margin-bottom:4px">Live Analysis Stream</div>'
                '<div style="font-size:12px;color:#7b8798;margin-bottom:10px">'
                "AI thinking steps stream here in real time via SSE &mdash; every reasoning stage, "
                "evidence finding and web citation appears as the model works. "
                "Results are saved and replayed on future views."
                "</div>",
                unsafe_allow_html=True,
            )
            _run_analysis_stream(ticker)

    # Weight editor (collapsible)
    _render_weight_editor(detail)

    # How to use (always visible at bottom)
    _render_how_to_use()

    # Footer
    st.markdown(
        '<div style="margin-top:32px;padding-top:14px;border-top:1px solid #e6ebf2;'
        'color:#7b8798;font-size:11px">'
        "StockForensics: scores computed deterministically in code. "
        "LLM provides qualitative synthesis only. Never says buy or sell. "
        "Educational research only."
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
