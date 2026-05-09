"""Deterministic stock-to-user fit scoring."""

from app.models.schemas import FitScore, FitScoreBreakdown


def _clamp(value: float, lower: float = 0.0, upper: float = 10.0) -> float:
    return max(lower, min(upper, value))


def _as_float(value: object, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _normalized_terms(values: list[str]) -> set[str]:
    return {value.lower().strip() for value in values if value.strip()}


def _risk_fit(profile: dict, valuation: dict) -> FitScoreBreakdown:
    risk_language = profile.get("risk_language", {})
    user_tolerance = _as_float(risk_language.get("tolerance"), 0.5)
    beta = _as_float(valuation.get("beta"), 1.0)
    beta_normalized = max(0.0, min(1.0, beta / 2.0))
    score = _clamp((1 - abs(user_tolerance - beta_normalized)) * 10)

    if beta_normalized > user_tolerance + 0.2:
        reason = "Volatility is above your usual comfort zone, but still close enough to consider."
    elif beta_normalized < user_tolerance - 0.2:
        reason = "Risk looks calmer than your usual target, which may trade upside for stability."
    else:
        reason = "Volatility lines up well with your stated risk tolerance."

    return FitScoreBreakdown(score=round(score, 1), reason=reason)


def _style_fit(profile: dict, valuation: dict) -> FitScoreBreakdown:
    interests = _normalized_terms(profile.get("thematic_interests", []))
    tags = _normalized_terms(valuation.get("sector_tags", []))

    if not interests:
        return FitScoreBreakdown(score=5.0, reason="No thematic interests are set yet, so style fit is neutral.")

    overlap = interests.intersection(tags)
    score = _clamp((len(overlap) / max(len(interests), 1)) * 10)

    if overlap:
        matched = ", ".join(sorted(overlap))
        reason = f"Matches your interest in {matched}."
    elif tags:
        reason = "Sector tags do not strongly overlap with your current interests."
    else:
        reason = "No sector tags are available yet, so style fit is neutral."
        score = 5.0

    return FitScoreBreakdown(score=round(score, 1), reason=reason)


def _classify_stock(valuation: dict) -> str:
    pe_forward = _as_float(valuation.get("pe_forward"), 25.0)
    momentum = _as_float(valuation.get("momentum_3m"), 0.0)

    if pe_forward >= 32 or momentum >= 12:
        return "growth"
    if pe_forward <= 18 and momentum < 8:
        return "value"
    return "balanced"


def _horizon_fit(profile: dict, valuation: dict) -> FitScoreBreakdown:
    horizon = str(profile.get("horizon", "")).lower()
    stock_class = _classify_stock(valuation)

    if stock_class == "growth" and any(term in horizon for term in ["6_months", "1_year", "2_year"]):
        score = 9.0
        reason = "Growth profile fits your medium-term holding window."
    elif stock_class == "balanced":
        score = 7.0
        reason = "Balanced profile can work across your current holding window."
    elif stock_class == "value" and any(term in horizon for term in ["2_year", "long", "5_year"]):
        score = 8.0
        reason = "Value profile may fit better with patience and a longer holding period."
    else:
        score = 5.0
        reason = "Time horizon is a partial fit, but not the clearest match."

    return FitScoreBreakdown(score=score, reason=reason)


def _conviction_fit(research: dict) -> FitScoreBreakdown:
    conviction = _as_float(research.get("conviction_signal"), 0.5)
    score = _clamp(conviction * 10)
    analyst_tone = str(research.get("analyst_tone", "neutral")).lower()

    if score >= 7.5:
        reason = f"Recent research tone is {analyst_tone}, giving the idea strong support."
    elif score >= 5.0:
        reason = f"Recent research tone is {analyst_tone}, so conviction is moderate."
    else:
        reason = f"Recent research tone is {analyst_tone}, so conviction is cautious."

    return FitScoreBreakdown(score=round(score, 1), reason=reason)


def compute_fit_score(profile: dict, research: dict, valuation: dict) -> FitScore:
    risk_fit = _risk_fit(profile, valuation)
    style_fit = _style_fit(profile, valuation)
    horizon_fit = _horizon_fit(profile, valuation)
    conviction = _conviction_fit(research)

    total = (
        0.40 * risk_fit.score
        + 0.25 * style_fit.score
        + 0.15 * horizon_fit.score
        + 0.20 * conviction.score
    )

    return FitScore(
        total=round(total, 1),
        breakdown={
            "risk_fit": risk_fit,
            "style_fit": style_fit,
            "horizon_fit": horizon_fit,
            "conviction": conviction,
        },
    )
