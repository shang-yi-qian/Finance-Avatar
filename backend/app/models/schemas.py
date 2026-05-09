from pydantic import BaseModel
from typing import Any, Optional, Literal


class PitchRequest(BaseModel):
    ticker: str
    user_id: str = "live_demo_user"
    profile: Optional[dict[str, Any]] = None


class FeedbackRequest(BaseModel):
    pitch_id: str
    user_id: str
    signal: Literal["too_jargony", "too_basic", "nailed_it"]


class OnboardRequest(BaseModel):
    user_id: str
    display_name: str
    risk_tolerance: float
    horizon: str
    thematic_interests: list[str]
    jargon_level: float


class FitScoreBreakdown(BaseModel):
    score: float
    reason: str


class FitScore(BaseModel):
    total: float
    breakdown: dict[str, FitScoreBreakdown]


class PitchResponse(BaseModel):
    ticker: str
    user_id: str
    pitch_id: Optional[str] = None
    fit_score: FitScore
    spoken_text: str
    audio_url: Optional[str] = None
    video_url: Optional[str] = None


class ProfileResponse(BaseModel):
    user_id: str
    tone: dict
    jargon_tolerance: dict
    risk_language: dict
    explanation_depth: str
    thematic_interests: list[str]
    horizon: str
    feedback_history: list
