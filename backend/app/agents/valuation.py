"""Valuation agent for Phase 2.

Uses Person B's Smithery service when available and falls back to local demo
data while API credentials are not set up.
"""

from typing import Any


ValuationResult = dict[str, Any]


def _report_context(
    analyst: str,
    earnings: str,
    quality: str,
    peers: list[str],
    valuation: str,
) -> dict[str, Any]:
    return {
        "analyst_context": {"summary": analyst},
        "earnings_context": {"summary": earnings},
        "quality_context": {"summary": quality},
        "peer_context": {"peers": peers, "summary": valuation},
    }


_FALLBACK_VALUATIONS: dict[str, ValuationResult] = {
    "NVDA": {
        "price": 920.0,
        "pe_trailing": 74.0,
        "pe_forward": 35.0,
        "eps": 12.4,
        "market_cap": 2_250_000_000_000,
        "beta": 1.65,
        "consensus": "buy",
        "momentum_3m": 18.0,
        "sector_tags": ["semiconductors", "AI infrastructure", "cloud"],
        **_report_context(
            analyst="Analyst setup is supportive, with upside still tied to AI infrastructure demand.",
            earnings="Recent earnings context looks strong, but expectations are already elevated.",
            quality="Quality profile is high, led by margins, scale, and data-center demand.",
            peers=["AMD", "AVGO", "TSM"],
            valuation="Premium valuation versus peers, but growth is also stronger than average.",
        ),
    },
    "TSLA": {
        "price": 175.0,
        "pe_trailing": 45.0,
        "pe_forward": 38.0,
        "eps": 3.9,
        "market_cap": 560_000_000_000,
        "beta": 2.1,
        "consensus": "hold",
        "momentum_3m": -6.0,
        "sector_tags": ["consumer tech", "EVs", "autonomy", "energy"],
        **_report_context(
            analyst="Analyst tone is mixed, with autonomy upside balanced against delivery and margin risk.",
            earnings="Recent earnings context is uneven, especially around margins and demand.",
            quality="Quality profile depends heavily on execution and cost control.",
            peers=["RIVN", "GM", "F"],
            valuation="Valuation still prices in future optionality more than current auto fundamentals.",
        ),
    },
    "MSFT": {
        "price": 430.0,
        "pe_trailing": 37.0,
        "pe_forward": 30.0,
        "eps": 11.6,
        "market_cap": 3_200_000_000_000,
        "beta": 0.9,
        "consensus": "buy",
        "momentum_3m": 9.0,
        "sector_tags": ["cloud", "AI infrastructure", "enterprise software"],
        **_report_context(
            analyst="Analyst setup is constructive, centered on Azure and AI monetization.",
            earnings="Recent earnings context is steady, with cloud growth doing most of the work.",
            quality="Quality profile is strong thanks to durable cash flow and diversified software demand.",
            peers=["GOOGL", "AMZN", "ORCL"],
            valuation="Valuation is not cheap, but quality and earnings consistency help support it.",
        ),
    },
    "SMR": {
        "price": None,
        "pe_trailing": None,
        "pe_forward": None,
        "eps": None,
        "market_cap": None,
        "beta": 1.85,
        "consensus": "hold",
        "momentum_3m": 0.0,
        "sector_tags": ["nuclear power", "energy", "clean energy", "small modular reactors"],
        **_report_context(
            analyst="Analyst setup is mixed: SMR offers nuclear optionality, but commercialization timing is still uncertain.",
            earnings="Recent earnings context is early-stage and milestone-driven, so cash burn and project timing matter.",
            quality="Quality profile is speculative because the business depends on execution, regulatory progress, and customer adoption.",
            peers=["BWXT", "CEG", "OKLO"],
            valuation="Valuation is driven more by future nuclear power optionality than current earnings.",
        ),
    },
    "BTC": {
        "price": 65000.0,
        "pe_trailing": None,
        "pe_forward": None,
        "eps": None,
        "market_cap": 1_280_000_000_000,
        "beta": 1.9,
        "consensus": "n/a",
        "momentum_3m": 12.0,
        "sector_tags": ["crypto", "digital assets", "macro"],
    },
    "ETH": {
        "price": 3200.0,
        "pe_trailing": None,
        "pe_forward": None,
        "eps": None,
        "market_cap": 385_000_000_000,
        "beta": 2.0,
        "consensus": "n/a",
        "momentum_3m": 8.0,
        "sector_tags": ["crypto", "digital assets", "developer platform"],
    },
}


def _default_valuation(ticker: str) -> ValuationResult:
    return {
        "price": None,
        "pe_trailing": None,
        "pe_forward": None,
        "eps": None,
        "market_cap": None,
        "beta": 1.0,
        "consensus": "unknown",
        "momentum_3m": 0.0,
        "sector_tags": [],
        "analyst_context": {},
        "earnings_context": {},
        "quality_context": {},
        "peer_context": {},
        "ticker": ticker,
    }


def _normalize_valuation(raw: Any, ticker: str) -> ValuationResult:
    if not isinstance(raw, dict):
        return _default_valuation(ticker)

    result = _default_valuation(ticker)
    result.update({key: value for key, value in raw.items() if value is not None})

    try:
        result["beta"] = float(result["beta"])
    except (TypeError, ValueError):
        result["beta"] = 1.0

    try:
        result["momentum_3m"] = float(result["momentum_3m"])
    except (TypeError, ValueError):
        result["momentum_3m"] = 0.0

    sector_tags = result.get("sector_tags")
    if not isinstance(sector_tags, list):
        result["sector_tags"] = []

    for key in ("analyst_context", "earnings_context", "quality_context", "peer_context"):
        if not isinstance(result.get(key), dict):
            result[key] = {}

    return result


def _enrich_with_fallback(live: ValuationResult, fallback: ValuationResult) -> ValuationResult:
    """Fill gaps in a live Shibui row without replacing live prices/market data."""
    if not fallback:
        return live
    enriched = dict(live)
    for key, value in fallback.items():
        if key == "sector_tags":
            current = enriched.get("sector_tags") if isinstance(enriched.get("sector_tags"), list) else []
            extra = value if isinstance(value, list) else []
            seen = {str(tag).lower() for tag in current}
            enriched["sector_tags"] = current + [tag for tag in extra if str(tag).lower() not in seen]
        elif key in {"analyst_context", "earnings_context", "quality_context", "peer_context"}:
            current = enriched.get(key) if isinstance(enriched.get(key), dict) else {}
            if not current and isinstance(value, dict):
                enriched[key] = value
        elif enriched.get(key) in (None, "", [], {}, "unknown"):
            enriched[key] = value
    return enriched


async def run_valuation(ticker: str) -> ValuationResult:
    normalized_ticker = ticker.upper().strip()
    fallback = _FALLBACK_VALUATIONS.get(normalized_ticker, _default_valuation(normalized_ticker))

    try:
        from app.services.smithery_service import get_fundamentals
    except ImportError:
        return fallback

    try:
        raw = await get_fundamentals(normalized_ticker)
    except Exception:
        # Demo resilience: if Smithery is not configured yet, keep /pitch working.
        return fallback

    if not raw:
        return fallback

    return _enrich_with_fallback(_normalize_valuation(raw, normalized_ticker), fallback)
