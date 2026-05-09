"""Spoken pitch synthesis.

The Phase 2 contract is a 60-90 word spoken pitch. Phase 3 layers in
adaptive phrasing: the same data is rendered in three jargon tiers based on
``profile.jargon_tolerance.level`` and any term in
``profile.jargon_tolerance.unknown_or_flagged`` is rephrased into plain
English. This is the demo beat — 👎 "too jargon-y" should produce an
audibly simpler pitch on the very next request.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.models.schemas import FitScore


# ---------------------------------------------------------------------------
# Tone helpers (unchanged behaviour)
# ---------------------------------------------------------------------------


def _tone_phrase(profile: dict) -> str:
    formality = float(profile.get("tone", {}).get("formality", 0.5))
    slang_examples = profile.get("tone", {}).get("slang_examples", [])

    if formality < 0.35 and slang_examples:
        return "lowkey"
    if formality > 0.7:
        return "overall"
    return "honestly"


def _verdict(total: float, jargon_level: float) -> str:
    if total >= 8.0:
        return "one of the stronger fits for you" if jargon_level >= 0.45 else "a really good match for you"
    if total >= 6.5:
        return "a pretty solid fit for you" if jargon_level >= 0.45 else "a good match for you"
    if total >= 5.0:
        return "a mixed but workable fit for you" if jargon_level >= 0.45 else "a so-so match — there are pros and cons"
    return "probably not the cleanest fit for you right now" if jargon_level >= 0.45 else "probably not a great match for you right now"


# ---------------------------------------------------------------------------
# Jargon-aware phrasing
# ---------------------------------------------------------------------------


def _jargon_tier(level: float) -> str:
    if level < 0.45:
        return "simple"
    if level < 0.7:
        return "medium"
    return "technical"


_CONSENSUS_FLAG_TRIGGERS = {
    "buy rating",
    "sell rating",
    "hold rating",
    "buy consensus",
    "sell consensus",
    "hold consensus",
    "analyst lean",
    "consensus",
    "rating snapshot",
}


def _consensus_phrase(consensus: str | None, tier: str, flagged: Iterable[str]) -> str:
    consensus_label = (consensus or "unknown").lower()
    flagged_lower = {term.lower() for term in flagged or [] if term}

    # If any consensus-flavoured term is flagged, drop straight to the simple
    # phrasing so the rewrite stays grammatical.
    if flagged_lower & {trigger.lower() for trigger in _CONSENSUS_FLAG_TRIGGERS}:
        effective_tier = "simple"
    else:
        effective_tier = tier

    if effective_tier == "simple":
        labels = {
            "buy": "analysts mostly say this looks like a thumbs up",
            "sell": "analysts mostly say this looks like a thumbs down",
            "hold": "analysts are split — they say wait and see",
            "n/a": "analyst views are not really a thing here",
            "unknown": "the analyst view is not super clear yet",
        }
    elif effective_tier == "medium":
        labels = {
            "buy": "the analyst lean is a buy rating",
            "sell": "the analyst lean is a sell rating",
            "hold": "the analyst lean is a hold rating",
            "n/a": "analyst ratings do not really apply here",
            "unknown": "analyst sentiment is not very clear yet",
        }
    else:
        labels = {
            "buy": "the street consensus is a buy",
            "sell": "the street consensus is a sell",
            "hold": "the street consensus is a hold",
            "n/a": "there is no traditional analyst consensus",
            "unknown": "the analyst consensus is unclear",
        }
    return labels.get(consensus_label, labels["unknown"])


def _shorten_reason(reason: str, tier: str) -> str:
    reason = (reason or "").rstrip(".")
    if tier == "simple":
        # Trim quoted/numerical noise so the simple version stays clean.
        reason = re.sub(r"\s*\([^)]*\)", "", reason)
    return reason


def _portfolio_context(ticker: str, profile: dict, tier: str) -> str:
    portfolio = profile.get("portfolio", [])
    if not isinstance(portfolio, list):
        return _no_position_line(tier)

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
        if tier == "simple":
            return f"You already own about {weight_pct:.0f}% of your money in this."
        if tier == "medium":
            return f"You already hold a {weight_pct:.0f}% {asset_type} position in this."
        return f"It is already a {weight_pct:.0f}% {asset_type} position in your portfolio."

    return _no_position_line(tier)


def _no_position_line(tier: str) -> str:
    if tier == "simple":
        return "You don't own any of this yet."
    if tier == "medium":
        return "You don't hold any of this in your portfolio yet."
    return "This would be a new position against your current portfolio."


def _format_money(value: object) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if abs(number) >= 1_000_000_000_000:
        return f"${number / 1_000_000_000_000:.1f}T"
    if abs(number) >= 1_000_000_000:
        return f"${number / 1_000_000_000:.1f}B"
    return f"${number:,.0f}"


def _analyst_target_line(price_target: dict, tier: str) -> str | None:
    target_price = _format_money(
        price_target.get("targetConsensus") or price_target.get("priceTargetConsensus")
    )
    if not target_price:
        return None
    if tier == "simple":
        return f"analysts think it could go up to about {target_price}"
    if tier == "medium":
        return f"the average analyst target is around {target_price}"
    return f"analyst consensus target is around {target_price}"


def _eps_line(estimate: dict, tier: str) -> str | None:
    eps_avg = estimate.get("epsAvg") or estimate.get("estimatedEpsAvg")
    if eps_avg is None:
        return None
    if tier == "simple":
        return f"the company is expected to make about {eps_avg} per share"
    if tier == "medium":
        return f"the next earnings estimate per share is about {eps_avg}"
    return f"future EPS estimate is about {eps_avg}"


def _rating_line(ratings: dict, tier: str) -> str | None:
    rating = ratings.get("rating") or ratings.get("overallRating")
    if not rating:
        return None
    if tier == "simple":
        return f"its overall analyst grade is {rating}"
    if tier == "medium":
        return f"the rating snapshot is {rating}"
    return f"rating snapshot is {rating}"


def _summary_or_keys(context: dict, fallback_keys: list[str]) -> str | None:
    summary = context.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip().rstrip(".")
    parts: list[str] = []
    for key in fallback_keys:
        value = context.get(key)
        if value not in (None, "", [], {}):
            parts.append(f"{key.replace('_', ' ')}: {value}")
    if not parts:
        return None
    return "; ".join(parts[:3]).rstrip(".")


def _report_context_line(valuation: dict, tier: str) -> str:
    analyst_context = valuation.get("analyst_context", {}) or {}
    target = analyst_context.get("price_target", {}) or {}
    estimate = analyst_context.get("next_estimate", {}) or {}
    ratings = analyst_context.get("ratings", {}) or {}

    analyst_parts = [
        line
        for line in (
            _analyst_target_line(target, tier),
            _eps_line(estimate, tier),
            _rating_line(ratings, tier),
        )
        if line
    ]
    if tier == "simple":
        # Keep it short and human.
        analyst_parts = analyst_parts[:1]
    elif tier == "medium":
        analyst_parts = analyst_parts[:2]

    analyst = ", and ".join(analyst_parts) if analyst_parts else _summary_or_keys(
        analyst_context,
        ["price_target", "ratings", "grade_summary", "next_estimate"],
    )
    earnings = _summary_or_keys(
        valuation.get("earnings_context", {}) or {},
        ["latest_earnings", "eps_surprise_pct", "growth"],
    )
    quality = _summary_or_keys(
        valuation.get("quality_context", {}) or {},
        ["piotroskiScore", "altmanZScore"],
    )
    peers = (valuation.get("peer_context", {}) or {}).get("peers", [])

    if tier == "simple":
        if analyst:
            return f"For context, {analyst}."
        if earnings:
            return f"For context, {earnings}."
        return ""

    if analyst:
        return f"Extra context: {analyst}."
    if earnings:
        return f"Extra context: {earnings}."
    if quality:
        return f"Quality check: {quality}."
    if isinstance(peers, list) and peers:
        return f"Peer set to compare: {', '.join(peers[:3])}."
    return ""


# ---------------------------------------------------------------------------
# Flagged-term replacement
# ---------------------------------------------------------------------------

# Plain-English equivalents used both when (a) a term is in the user's flagged
# list, and (b) the simple tier is active.
_PLAIN_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("P/E ratio", "valuation"),
    ("P/E", "valuation"),
    ("PE ratio", "valuation"),
    ("future EPS estimate", "expected earnings per share"),
    ("EPS estimate", "expected earnings per share"),
    ("EPS", "earnings per share"),
    ("buy consensus", "thumbs up from analysts"),
    ("sell consensus", "thumbs down from analysts"),
    ("hold consensus", "wait-and-see view from analysts"),
    ("buy rating", "thumbs up from analysts"),
    ("sell rating", "thumbs down from analysts"),
    ("hold rating", "wait-and-see view from analysts"),
    ("analyst lean", "what analysts think"),
    ("analyst consensus target", "average price target"),
    ("rating snapshot", "overall analyst grade"),
    ("DCF", "long-term cash flow estimate"),
    ("free cash flow", "spare cash the company makes"),
    ("Piotroski", "fundamentals score"),
    ("Altman", "bankruptcy risk score"),
    ("piotroskiScore", "fundamentals score"),
    ("altmanZScore", "bankruptcy risk score"),
    ("moving average", "trend line"),
    ("RSI", "momentum reading"),
    ("MACD", "momentum reading"),
    ("valuation multiple", "valuation"),
    ("beta", "how volatile it is"),
    ("consensus", "analyst view"),
    ("drawdown", "drop from the high"),
    ("bps", "basis points (small percentage steps)"),
    ("yield", "income rate"),
)


def _strip_flagged_terms(text: str, flagged: Iterable[str]) -> str:
    flagged_lower = {term.lower() for term in flagged or [] if term}
    if not flagged_lower:
        return text
    for term, replacement in _PLAIN_REPLACEMENTS:
        if term.lower() in flagged_lower:
            text = re.sub(rf"\b{re.escape(term)}\b", replacement, text, flags=re.IGNORECASE)
    return text


def _force_plain_english(text: str) -> str:
    for term, replacement in _PLAIN_REPLACEMENTS:
        text = re.sub(rf"\b{re.escape(term)}\b", replacement, text, flags=re.IGNORECASE)
    return text


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def synthesize_pitch(
    ticker: str,
    profile: dict,
    fit_score: FitScore,
    research: dict,
    valuation: dict,
) -> str:
    jargon_tolerance = profile.get("jargon_tolerance", {}) or {}
    jargon_level = float(jargon_tolerance.get("level", 0.55))
    flagged = jargon_tolerance.get("unknown_or_flagged") or []
    tier = _jargon_tier(jargon_level)

    tone = _tone_phrase(profile)
    total = fit_score.total
    style_reason = _shorten_reason(fit_score.breakdown["style_fit"].reason, tier)
    risk_reason = _shorten_reason(fit_score.breakdown["risk_fit"].reason, tier)
    conviction_reason = _shorten_reason(fit_score.breakdown["conviction"].reason, tier)

    news_summary = str(research.get("news_summary", "")).strip()
    if len(news_summary) > 240:
        # Trim at the last sentence boundary inside the budget so we don't
        # cut a live Exa summary mid-clause.
        clipped = news_summary[:240]
        boundary = max(clipped.rfind("."), clipped.rfind(";"))
        if boundary >= 120:
            news_summary = clipped[: boundary + 1]
        else:
            news_summary = clipped.rstrip(",;:- ") + "..."

    consensus_phrase = _consensus_phrase(valuation.get("consensus"), tier, flagged)
    portfolio_context = _portfolio_context(ticker, profile, tier)
    context_line = _report_context_line(valuation, tier)

    if tier == "simple":
        body = (
            f"{ticker} scores {total:.1f} for you, {tone} {_verdict(total, jargon_level)}. "
            f"{portfolio_context} The big reason is fit: {style_reason}. "
            f"On the analyst side, {consensus_phrase}, and the latest news says {news_summary} "
            f"{context_line} "
            f"The thing to watch out for is risk: {risk_reason}. {conviction_reason}."
        )
        body = _force_plain_english(body)
    else:
        body = (
            f"{ticker} scores {total:.1f} for you, {tone} {_verdict(total, jargon_level)}. "
            f"{portfolio_context} The main reason is fit: {style_reason}. "
            f"On the analyst side, {consensus_phrase}, and recent context says {news_summary} "
            f"{context_line} "
            f"The caveat is risk: {risk_reason}. {conviction_reason}."
        )

    body = _strip_flagged_terms(body, flagged)
    return re.sub(r"\s+", " ", body).strip()
