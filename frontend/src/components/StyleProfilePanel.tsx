import { useEffect, useState } from "react";
import { useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import { getProfile, profileToPanelProfile, type ProfileResponse } from "../lib/api";
import { buildStyleSummary, loadUserProfile } from "../lib/userProfile";

interface Props {
  userId?: string;
  refreshKey?: number;
}

export default function StyleProfilePanel({ userId, refreshKey = 0 }: Props) {
  const localProfile = loadUserProfile();
  const activeUserId = userId ?? localProfile.userId;
  const [profile, setProfile] = useState<ProfileResponse | null>(() => profileToPanelProfile(localProfile));
  const convexUser = useQuery(api.users.getUser, { userId: activeUserId });

  useEffect(() => {
    const latestLocalProfile = loadUserProfile();
    if (latestLocalProfile.userId === activeUserId) {
      setProfile(profileToPanelProfile(latestLocalProfile));
      return;
    }
    getProfile(activeUserId)
      .then(setProfile)
      .catch(() => setProfile(profileToPanelProfile(latestLocalProfile)));
  }, [activeUserId, refreshKey]);

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
    <div className="card style-panel">
      <h3>
        Your Style Profile
      </h3>

      {/* Jargon tolerance */}
      <div>
        <div className="profile-metric-header">
          <span>Jargon tolerance</span>
          <strong>
            {levelPct}%
          </strong>
        </div>
        <div className="score-bar-track">
          <div className="score-bar-fill" style={{ width: `${levelPct}%` }} />
        </div>
      </div>

      {/* Slang tags */}
      <div>
        <span className="profile-label">
          Tone markers
        </span>
        <div className="tag-list">
          {profile.tone.slang_examples.map((tag) => (
            <span className="tag" key={tag}>
              {tag}
            </span>
          ))}
        </div>
      </div>

      {(convexUser?.styleProfileSummary || profile) && (
        <div>
          <span className="profile-label">
            Live profile summary
          </span>
          <p className="profile-summary">
            {convexUser?.styleProfileSummary || buildStyleSummary(loadUserProfile())}
          </p>
        </div>
      )}

      {/* Flagged terms */}
      {profile.jargon_tolerance.unknown_or_flagged.length > 0 && (
        <div>
          <span className="profile-label">
            Flagged terms (avoid)
          </span>
          <div className="tag-list">
            {profile.jargon_tolerance.unknown_or_flagged.map((t) => (
              <span className="tag tag-danger" key={t}>
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
