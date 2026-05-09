from fastapi import APIRouter

from app.models.schemas import FeedbackRequest, FeedbackResponse, ProfileResponse
from app.services import adaption_service

router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(req: FeedbackRequest) -> FeedbackResponse:
    profile, flagged_added, delta = await adaption_service.apply_feedback(
        req.user_id,
        pitch_id=req.pitch_id,
        signal=req.signal,
        profile_snapshot=req.profile,
        ticker=req.ticker,
    )
    return FeedbackResponse(
        status="ok",
        signal=req.signal,
        pitch_id=req.pitch_id,
        profile=ProfileResponse.model_validate(profile),
        flagged_terms_added=flagged_added,
        jargon_level_delta=delta,
    )
