"""Phase 2 orchestrator.

Keeps the required tool order explicit:
research -> valuation -> fit_score -> synthesize.
"""

from uuid import uuid4

from app.agents.fit_score import compute_fit_score
from app.agents.research import run_research
from app.agents.synthesis import synthesize_pitch
from app.agents.valuation import run_valuation
from app.models.schemas import PitchResponse


async def run_orchestrator(ticker: str, profile: dict, user_id: str = "kai_demo") -> PitchResponse:
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

    return PitchResponse(
        ticker=normalized_ticker,
        user_id=user_id,
        pitch_id=f"phase2-{normalized_ticker.lower()}-{uuid4().hex[:8]}",
        fit_score=fit_score,
        spoken_text=spoken_text,
        audio_url=None,
        video_url=None,
    )
