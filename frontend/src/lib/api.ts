import type { LiveUserProfile } from "./userProfile";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface FitScoreBreakdown {
  score: number;
  reason: string;
}

export interface FitScore {
  total: number;
  breakdown: Record<string, FitScoreBreakdown>;
}

export interface ResearchSource {
  title: string;
  url: string;
  publishedDate: string | null;
}

export interface PortfolioContext {
  status: string;
  summary: string;
  current_weight: number | null;
  avg_cost: number | null;
}

export interface PitchReport {
  recommendation: string;
  headline: string;
  research_summary: string;
  earnings_sentiment: string;
  analyst_tone: string;
  valuation_snapshot: Record<string, unknown>;
  portfolio_context: PortfolioContext;
  key_takeaways: string[];
  risks: string[];
  sources: ResearchSource[];
}

export interface PitchResponse {
  ticker: string;
  user_id: string;
  pitch_id: string | null;
  fit_score: FitScore;
  spoken_text: string;
  report: PitchReport | null;
  audio_url: string | null;
  video_url: string | null;
}

export interface ProfileResponse {
  user_id: string;
  tone: { formality: number; emoji_usage: number; slang_examples: string[] };
  jargon_tolerance: { level: number; known_terms: string[]; unknown_or_flagged: string[] };
  risk_language: { tolerance: number; preferred_framing: string };
  explanation_depth: string;
  thematic_interests: string[];
  horizon: string;
  feedback_history: unknown[];
}

export async function postPitch(
  ticker: string,
  userId: string,
  profile?: Record<string, unknown>
): Promise<PitchResponse> {
  const res = await fetch(`${BASE}/pitch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, user_id: userId, profile }),
  });
  if (!res.ok) throw new Error(`/pitch failed: ${res.status}`);
  return res.json();
}

export interface FeedbackResponse {
  status: string;
  signal: "too_jargony" | "too_basic" | "nailed_it";
  pitch_id: string;
  profile: ProfileResponse;
  flagged_terms_added: string[];
  jargon_level_delta: number;
}

export async function postFeedback(
  pitchId: string,
  userId: string,
  signal: "too_jargony" | "too_basic" | "nailed_it",
  options: { ticker?: string; profile?: Record<string, unknown> } = {}
): Promise<FeedbackResponse> {
  const res = await fetch(`${BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pitch_id: pitchId,
      user_id: userId,
      signal,
      ticker: options.ticker,
      profile: options.profile,
    }),
  });
  if (!res.ok) throw new Error(`/feedback failed: ${res.status}`);
  return res.json();
}

export async function getProfile(userId: string): Promise<ProfileResponse> {
  const res = await fetch(`${BASE}/profile/${userId}`);
  if (!res.ok) throw new Error(`/profile failed: ${res.status}`);
  return res.json();
}

export function profileToPanelProfile(profile: LiveUserProfile): ProfileResponse {
  return {
    user_id: profile.userId,
    tone: { formality: profile.toneFormality, emoji_usage: 0.35, slang_examples: profile.slangExamples },
    jargon_tolerance: {
      level: profile.jargonLevel,
      known_terms: ["P/E", "EPS", "beta", "market cap"],
      unknown_or_flagged: profile.flaggedTerms ?? [],
    },
    risk_language: { tolerance: profile.riskTolerance, preferred_framing: "upside_first" },
    explanation_depth:
      profile.explanationDepth ?? (profile.jargonLevel < 0.45 ? "plain_english" : "medium"),
    thematic_interests: profile.thematicInterests,
    horizon: profile.horizon,
    feedback_history: [],
  };
}

export async function postOnboard(formData: FormData): Promise<{
  status: string;
  user_id: string;
  avatar_variants: string[];
  voice_id: string;
  voice_transcript: string;
  style_profile_patch: {
    transcript?: string;
    slang_examples?: string[];
    preferred_phrases?: string[];
    formality?: number;
    explanation_depth?: string;
    tone_summary?: string;
  };
}> {
  const res = await fetch(`${BASE}/onboard`, { method: "POST", body: formData });
  if (!res.ok) throw new Error(`/onboard failed: ${res.status}`);
  return res.json();
}
