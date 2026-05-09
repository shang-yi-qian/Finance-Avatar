from fastapi import APIRouter

from app.models.schemas import ProfileResponse
from app.services import adaption_service, profile_store

router = APIRouter()

# Kept for backwards compat with any callers that imported these names.
DEFAULT_PROFILE = ProfileResponse.model_validate(profile_store.DEFAULT_PROFILE)
KAI_DEMO_PROFILE = DEFAULT_PROFILE


@router.get("/profile/{user_id}", response_model=ProfileResponse)
async def get_profile(user_id: str) -> ProfileResponse:
    profile = adaption_service.get_profile(user_id)
    return ProfileResponse.model_validate(profile)
