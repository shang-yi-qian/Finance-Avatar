from fastapi import APIRouter
from app.models.schemas import PitchRequest, PitchResponse, FitScore, FitScoreBreakdown

router = APIRouter()

# Phase 1: hardcoded mock response — replaced in Phase 2 with real orchestrator
MOCK_PITCH = PitchResponse(
    ticker="NVDA",
    user_id="kai_demo",
    pitch_id="mock-pitch-001",
    fit_score=FitScore(
        total=8.4,
        breakdown={
            "risk_fit": FitScoreBreakdown(score=7.8, reason="Higher vol than usual, within range"),
            "style_fit": FitScoreBreakdown(score=9.5, reason="Core AI infra — right in your wheelhouse"),
            "horizon_fit": FitScoreBreakdown(score=8.1, reason="Growth profile suits 6–24 month window"),
            "conviction": FitScoreBreakdown(score=8.2, reason="Strong consensus + bullish news cycle"),
        },
    ),
    spoken_text=(
        "NVDA's an 8.4 for you — lowkey one of the better fits in your bag right now. "
        "Your AI infra tilt lines up perfectly and the momentum this week is solid. "
        "Risk's a bit spicy compared to your usual, but nothing you can't handle if you're in for the long game."
    ),
    audio_url=None,
)


@router.post("/pitch", response_model=PitchResponse)
async def pitch(req: PitchRequest):
    # Phase 2: replace with orchestrator.run(req.ticker, profile)
    response = MOCK_PITCH.model_copy(update={"ticker": req.ticker.upper(), "user_id": req.user_id})
    return response
