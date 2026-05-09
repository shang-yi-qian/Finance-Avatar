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
    profile: Optional[dict[str, Any]] = None
    ticker: Optional[str] = None


class FeedbackResponse(BaseModel):
    status: str
    signal: str
    pitch_id: str
    profile: "ProfileResponse"
    flagged_terms_added: list[str] = []
    jargon_level_delta: float = 0.0


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


class ResearchSource(BaseModel):
    title: str
    url: str
    publishedDate: Optional[str] = None


class PortfolioContext(BaseModel):
    status: str
    summary: str
    current_weight: Optional[float] = None
    avg_cost: Optional[float] = None
    diversification_note: Optional[str] = None


class PitchReport(BaseModel):
    recommendation: str
    headline: str
    research_summary: str
    earnings_sentiment: str
    analyst_tone: str
    valuation_snapshot: dict[str, Any]
    portfolio_context: PortfolioContext
    diversification_note: Optional[str] = None
    key_takeaways: list[str]
    risks: list[str]
    sources: list[ResearchSource] = []


class PitchResponse(BaseModel):
    ticker: str
    user_id: str
    pitch_id: Optional[str] = None
    fit_score: FitScore
    spoken_text: str
    report: Optional[PitchReport] = None
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


FeedbackResponse.model_rebuild()
