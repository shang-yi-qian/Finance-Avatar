from fastapi import APIRouter

from app.agents.orchestrator import run_orchestrator
from app.models.schemas import PitchRequest, PitchResponse
from app.services import adaption_service, profile_store

router = APIRouter()


@router.post("/pitch", response_model=PitchResponse)
async def pitch(req: PitchRequest) -> PitchResponse:
    # Merge the frontend snapshot with any server-side personalization state
    # (flagged terms, lowered jargon level, feedback history, ...).
    merged_profile = adaption_service.upsert_profile(req.user_id, req.profile)
    response = await run_orchestrator(req.ticker, merged_profile, user_id=req.user_id)

    # Remember the spoken text by pitch_id so /feedback can extract jargon
    # terms from the exact transcript the user reacted to.
    if response.pitch_id:
        profile_store.remember_pitch(
            response.pitch_id,
            user_id=req.user_id,
            ticker=response.ticker,
            spoken_text=response.spoken_text,
        )
    return response
