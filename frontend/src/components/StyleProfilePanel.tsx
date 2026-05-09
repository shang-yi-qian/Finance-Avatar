import { useEffect, useState } from "react";
import { getProfile, type ProfileResponse } from "../lib/api";

interface Props {
  userId?: string;
  refreshKey?: number;
}

export default function StyleProfilePanel({ userId = "kai_demo", refreshKey = 0 }: Props) {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);

  useEffect(() => {
    getProfile(userId)
      .then(setProfile)
      .catch(console.error);
  }, [userId, refreshKey]);

  if (!profile) {
    return (
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="skeleton" style={{ height: 14, width: "60%" }} />
        <div className="skeleton" style={{ height: 6, width: "100%" }} />
        <div className="skeleton" style={{ height: 28, width: "80%" }} />
      </div>
    );
  }

  const level = profile.jargon_tolerance.level;
  const levelPct = Math.round(level * 100);

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h3 style={{ fontSize: 14, color: "var(--text-dim)", fontWeight: 500, margin: 0 }}>
        Your Style Profile
      </h3>

      {/* Jargon tolerance */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
          <span style={{ fontSize: 13 }}>Jargon tolerance</span>
          <span style={{ fontSize: 13, color: "var(--accent-light)", fontWeight: 600 }}>
            {levelPct}%
          </span>
        </div>
        <div className="score-bar-track">
          <div className="score-bar-fill" style={{ width: `${levelPct}%` }} />
        </div>
      </div>

      {/* Slang tags */}
      <div>
        <span style={{ fontSize: 12, color: "var(--text-dim)", display: "block", marginBottom: 6 }}>
          Tone markers
        </span>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {profile.tone.slang_examples.map((tag) => (
            <span
              key={tag}
              style={{
                padding: "3px 10px",
                borderRadius: 99,
                background: "var(--bg-input)",
                border: "1px solid var(--border)",
                fontSize: 12,
                color: "var(--accent-light)",
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      {/* Flagged terms */}
      {profile.jargon_tolerance.unknown_or_flagged.length > 0 && (
        <div>
          <span style={{ fontSize: 12, color: "var(--text-dim)", display: "block", marginBottom: 6 }}>
            Flagged terms (avoid)
          </span>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {profile.jargon_tolerance.unknown_or_flagged.map((t) => (
              <span
                key={t}
                style={{
                  padding: "3px 10px",
                  borderRadius: 99,
                  background: "rgba(239,68,68,0.1)",
                  border: "1px solid rgba(239,68,68,0.3)",
                  fontSize: 12,
                  color: "var(--red)",
                }}
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
