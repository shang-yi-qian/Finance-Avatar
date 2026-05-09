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
  riskTolerance: number;
  jargonLevel: number;
  horizon: string;
  experience: string;
  thematicInterests: string[];
  portfolio: PortfolioHolding[];
};

export const ACTIVE_PROFILE_KEY = "pitchsnap:activeProfile";
export const SELECTED_AVATAR_KEY = "pitchsnap:selectedAvatar";

export const DEFAULT_USER_PROFILE: LiveUserProfile = {
  userId: "live_demo_user",
  displayName: "Demo User",
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
  return (
    `${profile.displayName}: risk ${Math.round(profile.riskTolerance * 100)}%, ` +
    `jargon ${Math.round(profile.jargonLevel * 100)}%, ${profile.horizon.replaceAll("_", " ")}, ` +
    `${interests}, assets: ${assetTypes || "none"}`
  );
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
      formality: 0.25,
      emoji_usage: 0.35,
      slang_examples: ["lowkey", "ngl"],
    },
    jargon_tolerance: {
      level: profile.jargonLevel,
      known_terms: ["P/E", "EPS", "beta", "market cap"],
      unknown_or_flagged: [],
    },
    explanation_depth: profile.jargonLevel < 0.45 ? "plain_english" : "medium",
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

