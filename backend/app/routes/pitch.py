from fastapi import APIRouter
from app.agents.orchestrator import run_orchestrator
from app.models.schemas import PitchRequest, PitchResponse
from app.routes.profile import KAI_DEMO_PROFILE

router = APIRouter()


@router.post("/pitch", response_model=PitchResponse)
async def pitch(req: PitchRequest):
    profile = req.profile or KAI_DEMO_PROFILE.model_dump()
    return await run_orchestrator(req.ticker, profile, user_id=req.user_id)
