const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface FitScoreBreakdown {
  score: number;
  reason: string;
}

export interface FitScore {
  total: number;
  breakdown: Record<string, FitScoreBreakdown>;
}

export interface PitchResponse {
  ticker: string;
  user_id: string;
  pitch_id: string | null;
  fit_score: FitScore;
  spoken_text: string;
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

export async function postPitch(ticker: string, userId = "kai_demo"): Promise<PitchResponse> {
  const res = await fetch(`${BASE}/pitch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, user_id: userId }),
  });
  if (!res.ok) throw new Error(`/pitch failed: ${res.status}`);
  return res.json();
}

export async function postFeedback(
  pitchId: string,
  userId: string,
  signal: "too_jargony" | "too_basic" | "nailed_it"
): Promise<void> {
  const res = await fetch(`${BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pitch_id: pitchId, user_id: userId, signal }),
  });
  if (!res.ok) throw new Error(`/feedback failed: ${res.status}`);
}

export async function getProfile(userId: string): Promise<ProfileResponse> {
  const res = await fetch(`${BASE}/profile/${userId}`);
  if (!res.ok) throw new Error(`/profile failed: ${res.status}`);
  return res.json();
}

export async function postOnboard(formData: FormData): Promise<{
  user_id: string;
  avatar_variants: string[];
  voice_id: string;
}> {
  const res = await fetch(`${BASE}/onboard`, { method: "POST", body: formData });
  if (!res.ok) throw new Error(`/onboard failed: ${res.status}`);
  return res.json();
}
