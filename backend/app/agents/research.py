"""Research agent for Phase 2.

This module intentionally works without API keys. If Person B adds
app.services.exa_service.search, this agent will use it; otherwise it returns
deterministic demo-safe research so the orchestrator can be built and tested.
"""

from typing import Any


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
            f"{ticker} has no live Exa data yet in local dev, so this is a "
            "placeholder research summary for pipeline testing."
        ),
        "earnings_sentiment": "Unknown until the Exa service is connected.",
        "analyst_tone": "neutral",
        "conviction_signal": 0.5,
    }


def _normalize_research(raw: Any, ticker: str) -> ResearchResult:
    if not isinstance(raw, dict):
        return _default_research(ticker)

    result = _default_research(ticker)
    result.update({key: value for key, value in raw.items() if value is not None})

    try:
        conviction = float(result["conviction_signal"])
    except (TypeError, ValueError):
        conviction = 0.5

    result["conviction_signal"] = max(0.0, min(1.0, conviction))
    return result


async def run_research(ticker: str) -> ResearchResult:
    normalized_ticker = ticker.upper().strip()

    try:
        from app.services.exa_service import search
    except ImportError:
        return _FALLBACK_RESEARCH.get(normalized_ticker, _default_research(normalized_ticker))

    raw = await search(normalized_ticker, days=7)
    return _normalize_research(raw, normalized_ticker)
