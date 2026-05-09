from fastapi import APIRouter
from app.models.schemas import ProfileResponse

router = APIRouter()

# Fallback only. The frontend sends a live profile snapshot from onboarding.
DEFAULT_PROFILE = ProfileResponse(
    user_id="live_demo_user",
    tone={"formality": 0.25, "emoji_usage": 0.35, "slang_examples": ["lowkey", "bag", "ngl", "fam"]},
    jargon_tolerance={"level": 0.55, "known_terms": ["P/E", "EPS", "beta", "market cap"], "unknown_or_flagged": []},
    risk_language={"tolerance": 0.72, "preferred_framing": "upside_first"},
    explanation_depth="medium",
    thematic_interests=["semiconductors", "AI infrastructure", "cloud", "consumer tech", "crypto"],
    horizon="6_months_to_2_years",
    feedback_history=[],
)
KAI_DEMO_PROFILE = DEFAULT_PROFILE


@router.get("/profile/{user_id}", response_model=ProfileResponse)
async def get_profile(user_id: str):
    # Phase 3: replace with adaption_service.get_profile(user_id)
    return DEFAULT_PROFILE.model_copy(update={"user_id": user_id})
