from fastapi import APIRouter
from app.models.schemas import FeedbackRequest

router = APIRouter()


@router.post("/feedback")
async def feedback(req: FeedbackRequest):
    # Phase 3: call adaption_service.update_profile() and save to Convex
    return {"status": "ok", "signal": req.signal, "pitch_id": req.pitch_id}
