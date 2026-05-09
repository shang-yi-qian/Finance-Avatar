"""Research agent.

Phase 2 / sponsor track: Exa-backed semantic news search.

If ``app.services.exa_service.search`` is configured (``EXA_API_KEY`` is
set), this agent returns the live bundle: a 1-2 sentence ``news_summary``,
``earnings_sentiment``, ``analyst_tone``, ``conviction_signal`` and a list
of ``sources``. If Exa cannot be reached we fall through to a deterministic
demo-safe payload so the pitch loop never breaks.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

ResearchResult = dict[str, Any]


_FALLBACK_RESEARCH: dict[str, ResearchResult] = {
    "NVDA": {
        "news_summary": (
            "Nvidia remains tied to strong AI infrastructure demand, with recent "
            "coverage focused on data-center GPU sales and supply constraints."
        ),
        "earnings_sentiment": "Positive: demand commentary remains strong, though expectations are high.",
        "analyst_tone": "bullish",
        "conviction_signal": 0.82,
    },
    "TSLA": {
        "news_summary": (
            "Tesla sentiment is mixed, with investors balancing margin pressure, "
            "delivery trends, autonomy updates, and energy growth."
        ),
        "earnings_sentiment": "Mixed: growth story is intact, but margins and demand need watching.",
        "analyst_tone": "neutral",
        "conviction_signal": 0.58,
    },
    "MSFT": {
        "news_summary": (
            "Microsoft continues to benefit from cloud demand and AI product "
            "integration across Azure, Office, and developer tools."
        ),
        "earnings_sentiment": "Positive: cloud and AI monetization remain the core story.",
        "analyst_tone": "bullish",
        "conviction_signal": 0.76,
    },
}


def _default_research(ticker: str) -> ResearchResult:
    return {
        "news_summary": (
            f"{ticker} has no live Exa data right now, so this is a "
            "placeholder research summary for pipeline testing."
        ),
        "earnings_sentiment": "Unknown until the Exa service is reachable.",
        "analyst_tone": "neutral",
        "conviction_signal": 0.5,
        "sources": [],
    }


def _normalize_research(raw: Any, ticker: str) -> ResearchResult:
    if not isinstance(raw, dict):
        return _default_research(ticker)

    result = _default_research(ticker)
    for key, value in raw.items():
        if value is None:
            continue
        result[key] = value

    try:
        conviction = float(result["conviction_signal"])
    except (TypeError, ValueError):
        conviction = 0.5
    result["conviction_signal"] = max(0.0, min(1.0, conviction))

    tone = str(result.get("analyst_tone") or "").strip().lower()
    if tone not in {"bullish", "neutral", "bearish"}:
        tone = "neutral"
    result["analyst_tone"] = tone

    sources = result.get("sources")
    if not isinstance(sources, list):
        result["sources"] = []

    return result


def _fallback(ticker: str) -> ResearchResult:
    base = _FALLBACK_RESEARCH.get(ticker, _default_research(ticker))
    enriched = dict(base)
    enriched.setdefault("sources", [])
    return enriched


async def run_research(ticker: str) -> ResearchResult:
    normalized_ticker = ticker.upper().strip()

    try:
        from app.services.exa_service import ExaServiceError, search
    except ImportError:
        return _fallback(normalized_ticker)

    try:
        raw = await search(normalized_ticker, days=7)
    except ExaServiceError as exc:
        logger.info("Exa unavailable for %s, using fallback: %s", normalized_ticker, exc)
        return _fallback(normalized_ticker)
    except Exception as exc:  # noqa: BLE001 - never let the pipeline die on research
        logger.warning("Exa raised unexpected error for %s: %s", normalized_ticker, exc)
        return _fallback(normalized_ticker)

    if not raw:
        return _fallback(normalized_ticker)

    return _normalize_research(raw, normalized_ticker)
