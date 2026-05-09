from fastapi import APIRouter
from app.models.schemas import ProfileResponse

router = APIRouter()

# Phase 1: hardcoded Kai demo profile — replaced in Phase 3 with Adaption API call
KAI_DEMO_PROFILE = ProfileResponse(
    user_id="kai_demo",
    tone={"formality": 0.25, "emoji_usage": 0.35, "slang_examples": ["lowkey", "bag", "ngl", "fam"]},
    jargon_tolerance={"level": 0.55, "known_terms": ["P/E", "EPS", "beta", "market cap"], "unknown_or_flagged": []},
    risk_language={"tolerance": 0.72, "preferred_framing": "upside_first"},
    explanation_depth="medium",
    thematic_interests=["semiconductors", "AI infrastructure", "cloud", "consumer tech"],
    horizon="6_months_to_2_years",
    feedback_history=[],
)


@router.get("/profile/{user_id}", response_model=ProfileResponse)
async def get_profile(user_id: str):
    # Phase 3: replace with adaption_service.get_profile(user_id)
    return KAI_DEMO_PROFILE
