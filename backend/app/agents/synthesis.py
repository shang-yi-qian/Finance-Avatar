"""Spoken pitch synthesis.

The Phase 2 contract is a 60-90 word spoken pitch. This implementation is
deterministic for local development; an LLM-backed version can replace this
function later without changing the orchestrator contract.
"""

from app.models.schemas import FitScore


def _tone_phrase(profile: dict) -> str:
    formality = float(profile.get("tone", {}).get("formality", 0.5))
    slang_examples = profile.get("tone", {}).get("slang_examples", [])

    if formality < 0.35 and slang_examples:
        return "lowkey"
    if formality > 0.7:
        return "overall"
    return "honestly"


def _verdict(total: float) -> str:
    if total >= 8.0:
        return "one of the stronger fits for you"
    if total >= 6.5:
        return "a pretty solid fit for you"
    if total >= 5.0:
        return "a mixed but workable fit for you"
    return "probably not the cleanest fit for you right now"


def _shorten_reason(reason: str) -> str:
    return reason.rstrip(".")


def _portfolio_context(ticker: str, profile: dict) -> str:
    portfolio = profile.get("portfolio", [])
    if not isinstance(portfolio, list):
        return "This would be a new position against your current portfolio."

    for holding in portfolio:
        if not isinstance(holding, dict):
            continue
        if str(holding.get("ticker", "")).upper() != ticker.upper():
            continue
        weight = holding.get("weight", 0)
        asset_type = str(holding.get("asset_type") or holding.get("assetType") or "holding")
        try:
            weight_pct = float(weight) * 100
        except (TypeError, ValueError):
            weight_pct = 0
        return f"It is already a {weight_pct:.0f}% {asset_type} position in your portfolio."

    return "This would be a new position against your current portfolio."


async def synthesize_pitch(
    ticker: str,
    profile: dict,
    fit_score: FitScore,
    research: dict,
    valuation: dict,
) -> str:
    tone = _tone_phrase(profile)
    total = fit_score.total
    style_reason = _shorten_reason(fit_score.breakdown["style_fit"].reason)
    risk_reason = _shorten_reason(fit_score.breakdown["risk_fit"].reason)
    conviction_reason = _shorten_reason(fit_score.breakdown["conviction"].reason)
    news_summary = str(research.get("news_summary", "")).strip()
    consensus = valuation.get("consensus", "unknown")
    portfolio_context = _portfolio_context(ticker, profile)

    if len(news_summary) > 150:
        news_summary = news_summary[:147].rstrip() + "..."

    return (
        f"{ticker} scores {total:.1f} for you, {tone} { _verdict(total) }. "
        f"{portfolio_context} The main reason is fit: {style_reason}. The setup also has a {consensus} "
        f"consensus, and recent context says {news_summary} "
        f"The caveat is risk: {risk_reason}. {conviction_reason}."
    )
