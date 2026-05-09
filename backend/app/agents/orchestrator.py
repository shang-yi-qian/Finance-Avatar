"""Phase 2 orchestrator.

Keeps the required tool order explicit:
research -> valuation -> fit_score -> synthesize.
"""

from uuid import uuid4

from app.agents.fit_score import compute_fit_score
from app.agents.research import run_research
from app.agents.synthesis import synthesize_pitch
from app.agents.valuation import run_valuation
from app.models.schemas import PitchReport, PitchResponse, PortfolioContext, ResearchSource
from app.services.elevenlabs_service import generate_speech


def _fmt_money(value: object) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if abs(number) >= 1_000_000_000_000:
        return f"${number / 1_000_000_000_000:.1f}T"
    if abs(number) >= 1_000_000_000:
        return f"${number / 1_000_000_000:.1f}B"
    if abs(number) >= 1_000:
        return f"${number:,.0f}"
    return f"${number:,.2f}"


def _recommendation(total: float) -> str:
    if total >= 8:
        return "Strong fit"
    if total >= 6.5:
        return "Good fit"
    if total >= 5:
        return "Watchlist"
    return "Skip for now"


def _portfolio_context(ticker: str, profile: dict) -> PortfolioContext:
    portfolio = profile.get("portfolio") or []
    if not isinstance(portfolio, list):
        return PortfolioContext(
            status="new",
            summary="No portfolio snapshot was provided, so this is treated as a new idea.",
        )

    for holding in portfolio:
        if not isinstance(holding, dict):
            continue
        if str(holding.get("ticker", "")).upper() != ticker:
            continue
        try:
            weight = float(holding.get("weight", 0))
        except (TypeError, ValueError):
            weight = 0.0
        avg_cost = holding.get("avg_cost", holding.get("avgCost"))
        try:
            avg_cost_num = float(avg_cost) if avg_cost is not None else None
        except (TypeError, ValueError):
            avg_cost_num = None
        return PortfolioContext(
            status="owned",
            summary=f"You already own {ticker}; it is about {weight * 100:.0f}% of the portfolio snapshot.",
            current_weight=weight,
            avg_cost=avg_cost_num,
        )

    tickers = [str(h.get("ticker", "")).upper() for h in portfolio if isinstance(h, dict)]
    tickers = [value for value in tickers if value]
    suffix = f" Current holdings include {', '.join(tickers[:5])}." if tickers else ""
    return PortfolioContext(
        status="new",
        summary=f"{ticker} would be a new position against the current portfolio.{suffix}",
    )


def _valuation_snapshot(valuation: dict) -> dict:
    analyst_context = valuation.get("analyst_context") or {}
    target = analyst_context.get("price_target") or {}
    next_estimate = analyst_context.get("next_estimate") or {}
    peers = (valuation.get("peer_context") or {}).get("peers") or []
    target_price = target.get("targetConsensus") or target.get("priceTargetConsensus")
    return {
        "price": _fmt_money(valuation.get("price")),
        "market_cap": _fmt_money(valuation.get("market_cap")),
        "pe_trailing": valuation.get("pe_trailing"),
        "pe_forward": valuation.get("pe_forward"),
        "eps": valuation.get("eps"),
        "beta": valuation.get("beta"),
        "consensus": valuation.get("consensus", "unknown"),
        "momentum_3m": valuation.get("momentum_3m"),
        "analyst_target": _fmt_money(target_price),
        "next_eps_estimate": next_estimate.get("epsAvg") or next_estimate.get("estimatedEpsAvg"),
        "sector_tags": valuation.get("sector_tags") or [],
        "peers": peers[:5] if isinstance(peers, list) else [],
    }


def _report_sources(research: dict) -> list[ResearchSource]:
    sources = research.get("sources") or []
    out: list[ResearchSource] = []
    for source in sources[:5]:
        if not isinstance(source, dict):
            continue
        title = str(source.get("title") or "").strip()
        url = str(source.get("url") or "").strip()
        if title and url:
            out.append(
                ResearchSource(
                    title=title,
                    url=url,
                    publishedDate=source.get("publishedDate"),
                )
            )
    return out


def _build_report(
    *,
    ticker: str,
    profile: dict,
    research: dict,
    valuation: dict,
    fit_score,
) -> PitchReport:
    total = fit_score.total
    recommendation = _recommendation(total)
    snapshot = _valuation_snapshot(valuation)
    portfolio = _portfolio_context(ticker, profile)
    breakdown = fit_score.breakdown
    risk = breakdown["risk_fit"]
    style = breakdown["style_fit"]
    conviction = breakdown["conviction"]

    headline = (
        f"{recommendation}: {ticker} scores {total:.1f}/10 because "
        f"{style.reason.rstrip('.').lower()} and {conviction.reason.rstrip('.').lower()}."
    )

    key_takeaways = [
        f"Research: {research.get('news_summary', 'No recent research summary available.')}",
        f"Portfolio: {portfolio.summary}",
        f"Valuation: consensus is {snapshot['consensus']}; beta is {snapshot['beta']}; analyst target is {snapshot['analyst_target'] or 'unknown'}.",
    ]
    if snapshot["sector_tags"]:
        key_takeaways.append(f"Themes detected: {', '.join(snapshot['sector_tags'][:5])}.")

    risks = [risk.reason]
    if snapshot.get("pe_forward"):
        try:
            pe_forward = float(snapshot["pe_forward"])
            if pe_forward >= 35:
                risks.append("Valuation is demanding, so the stock needs continued earnings growth to justify the price.")
        except (TypeError, ValueError):
            pass
    earnings = str(research.get("earnings_sentiment") or "")
    if "concern" in earnings.lower() or "miss" in earnings.lower() or "pressure" in earnings.lower():
        risks.append(earnings)

    return PitchReport(
        recommendation=recommendation,
        headline=headline,
        research_summary=str(research.get("news_summary") or ""),
        earnings_sentiment=str(research.get("earnings_sentiment") or "Unknown"),
        analyst_tone=str(research.get("analyst_tone") or "neutral"),
        valuation_snapshot=snapshot,
        portfolio_context=portfolio,
        key_takeaways=key_takeaways[:5],
        risks=risks[:4],
        sources=_report_sources(research),
    )


async def run_orchestrator(ticker: str, profile: dict, user_id: str = "live_demo_user") -> PitchResponse:
    normalized_ticker = ticker.upper().strip()

    research = await run_research(normalized_ticker)
    valuation = await run_valuation(normalized_ticker)
    fit_score = compute_fit_score(profile, research, valuation)
    spoken_text = await synthesize_pitch(
        ticker=normalized_ticker,
        profile=profile,
        fit_score=fit_score,
        research=research,
        valuation=valuation,
    )
    audio_url = await generate_speech(
        text=spoken_text,
        voice_id=profile.get("voice_id"),
        user_id=user_id,
        ticker=normalized_ticker,
    )
    report = _build_report(
        ticker=normalized_ticker,
        profile=profile,
        research=research,
        valuation=valuation,
        fit_score=fit_score,
    )

    return PitchResponse(
        ticker=normalized_ticker,
        user_id=user_id,
        pitch_id=f"phase2-{normalized_ticker.lower()}-{uuid4().hex[:8]}",
        fit_score=fit_score,
        spoken_text=spoken_text,
        report=report,
        audio_url=audio_url,
        video_url=None,
    )
