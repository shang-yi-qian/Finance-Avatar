export type AssetType = "stock" | "etf" | "crypto";

export type PortfolioHolding = {
  id: string;
  ticker: string;
  assetType: AssetType;
  weight: number;
  avgCost: number;
};

export type LiveUserProfile = {
  userId: string;
  displayName: string;
  avatarImageUrl?: string;
  voiceId?: string;
  voicePrompt?: string;
  voiceTranscript?: string;
  slangExamples: string[];
  preferredPhrases: string[];
  toneFormality: number;
  riskTolerance: number;
  jargonLevel: number;
  horizon: string;
  experience: string;
  thematicInterests: string[];
  portfolio: PortfolioHolding[];
  flaggedTerms?: string[];
  explanationDepth?: string;
};

export const ACTIVE_PROFILE_KEY = "pitchsnap:activeProfile";
export const SELECTED_AVATAR_KEY = "pitchsnap:selectedAvatar";

export const DEFAULT_USER_PROFILE: LiveUserProfile = {
  userId: "live_demo_user",
  displayName: "Demo User",
  voicePrompt: "Tell me about one investment you like, one you avoid, and how you explain risk to a friend.",
  voiceTranscript: "",
  slangExamples: ["honestly", "I like", "I worry"],
  preferredPhrases: ["fits my risk", "long-term setup"],
  toneFormality: 0.35,
  riskTolerance: 0.72,
  jargonLevel: 0.55,
  horizon: "6_months_to_2_years",
  experience: "intermediate",
  thematicInterests: ["semiconductors", "AI infrastructure", "cloud", "consumer tech"],
  portfolio: [
    { id: "holding-nvda", ticker: "NVDA", assetType: "stock", weight: 0.28, avgCost: 480 },
    { id: "holding-msft", ticker: "MSFT", assetType: "stock", weight: 0.2, avgCost: 380 },
    { id: "holding-btc", ticker: "BTC", assetType: "crypto", weight: 0.08, avgCost: 65000 },
  ],
  flaggedTerms: [],
  explanationDepth: "medium",
};

export function createUserId(displayName: string) {
  const slug = displayName
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return slug ? `${slug}_profile` : DEFAULT_USER_PROFILE.userId;
}

export function buildStyleSummary(profile: LiveUserProfile) {
  const interests = profile.thematicInterests.slice(0, 3).join(", ") || "custom interests";
  const assetTypes = Array.from(new Set(profile.portfolio.map((holding) => holding.assetType))).join(", ");
  const lingo = profile.slangExamples.slice(0, 3).join(", ") || "live voice sample pending";
  const flaggedSegment =
    profile.flaggedTerms && profile.flaggedTerms.length > 0
      ? `, avoiding: ${profile.flaggedTerms.slice(0, 3).join(", ")}`
      : "";
  return (
    `${profile.displayName}: risk ${Math.round(profile.riskTolerance * 100)}%, ` +
    `jargon ${Math.round(profile.jargonLevel * 100)}%, ${profile.horizon.replaceAll("_", " ")}, ` +
    `${interests}, assets: ${assetTypes || "none"}, lingo: ${lingo}${flaggedSegment}`
  );
}

export type BackendProfileSnapshot = {
  jargon_tolerance?: { level?: number; unknown_or_flagged?: string[] };
  explanation_depth?: string;
};

export function applyBackendProfileToLocal(
  profile: LiveUserProfile,
  remote: BackendProfileSnapshot
): LiveUserProfile {
  const next: LiveUserProfile = { ...profile };
  const jargon = remote.jargon_tolerance ?? {};
  if (typeof jargon.level === "number" && Number.isFinite(jargon.level)) {
    next.jargonLevel = jargon.level;
  }
  if (Array.isArray(jargon.unknown_or_flagged)) {
    next.flaggedTerms = [...jargon.unknown_or_flagged];
  }
  if (remote.explanation_depth) {
    next.explanationDepth = remote.explanation_depth;
  }
  return next;
}

export function loadUserProfile(): LiveUserProfile {
  if (typeof window === "undefined") return DEFAULT_USER_PROFILE;
  const raw = window.localStorage.getItem(ACTIVE_PROFILE_KEY);
  if (!raw) return DEFAULT_USER_PROFILE;

  try {
    const parsed = JSON.parse(raw) as Partial<LiveUserProfile>;
    return {
      ...DEFAULT_USER_PROFILE,
      ...parsed,
      portfolio: Array.isArray(parsed.portfolio) && parsed.portfolio.length > 0
        ? parsed.portfolio
        : DEFAULT_USER_PROFILE.portfolio,
      thematicInterests:
        Array.isArray(parsed.thematicInterests) && parsed.thematicInterests.length > 0
          ? parsed.thematicInterests
          : DEFAULT_USER_PROFILE.thematicInterests,
      slangExamples:
        Array.isArray(parsed.slangExamples) && parsed.slangExamples.length > 0
          ? parsed.slangExamples
          : DEFAULT_USER_PROFILE.slangExamples,
      preferredPhrases:
        Array.isArray(parsed.preferredPhrases) && parsed.preferredPhrases.length > 0
          ? parsed.preferredPhrases
          : DEFAULT_USER_PROFILE.preferredPhrases,
      flaggedTerms: Array.isArray(parsed.flaggedTerms) ? parsed.flaggedTerms : [],
      explanationDepth: parsed.explanationDepth ?? DEFAULT_USER_PROFILE.explanationDepth,
    };
  } catch {
    return DEFAULT_USER_PROFILE;
  }
}

export function saveUserProfile(profile: LiveUserProfile) {
  window.localStorage.setItem(ACTIVE_PROFILE_KEY, JSON.stringify(profile));
  if (profile.avatarImageUrl) {
    window.localStorage.setItem(SELECTED_AVATAR_KEY, profile.avatarImageUrl);
  }
}

export function toBackendProfile(profile: LiveUserProfile) {
  return {
    user_id: profile.userId,
    voice_id: profile.voiceId,
    voice_transcript: profile.voiceTranscript,
    preferred_phrases: profile.preferredPhrases,
    portfolio: profile.portfolio.map(({ ticker, assetType, weight, avgCost }) => ({
      ticker,
      asset_type: assetType,
      weight,
      avg_cost: avgCost,
    })),
    risk_language: {
      tolerance: profile.riskTolerance,
      preferred_framing: "upside_first",
    },
    tone: {
      formality: profile.toneFormality,
      emoji_usage: 0.35,
      slang_examples: profile.slangExamples,
    },
    jargon_tolerance: {
      level: profile.jargonLevel,
      known_terms: ["P/E", "EPS", "beta", "market cap"],
      unknown_or_flagged: profile.flaggedTerms ?? [],
    },
    explanation_depth:
      profile.explanationDepth ?? (profile.jargonLevel < 0.45 ? "plain_english" : "medium"),
    thematic_interests: profile.thematicInterests,
    horizon: profile.horizon,
    experience: profile.experience,
  };
}

export function toConvexPortfolio(profile: LiveUserProfile) {
  return profile.portfolio.map(({ ticker, assetType, weight, avgCost }) => ({
    ticker,
    assetType,
    weight,
    avgCost,
  }));
}
