"""Valuation agent for Phase 2.

Uses Person B's Smithery service when available and falls back to local demo
data while API credentials are not set up.
"""

from typing import Any


ValuationResult = dict[str, Any]


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

    return result


async def run_valuation(ticker: str) -> ValuationResult:
    normalized_ticker = ticker.upper().strip()

    try:
        from app.services.smithery_service import get_fundamentals
    except ImportError:
        return _FALLBACK_VALUATIONS.get(normalized_ticker, _default_valuation(normalized_ticker))

    raw = await get_fundamentals(normalized_ticker)
    return _normalize_valuation(raw, normalized_ticker)
