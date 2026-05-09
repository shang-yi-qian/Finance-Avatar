import { useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import { loadUserProfile } from "../lib/userProfile";

export default function History() {
  const activeProfile = loadUserProfile();
  const pitches = useQuery(api.pitches.getPitchesByUser, { userId: activeProfile.userId });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, marginBottom: 4 }}>Pitch History</h1>
          <p style={{ color: "var(--text-dim)" }}>Recent Convex pitch records for {activeProfile.displayName}.</p>
        </div>
      </div>

      {pitches === undefined && (
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="skeleton" style={{ height: 18, width: "28%" }} />
          <div className="skeleton" style={{ height: 70, width: "100%" }} />
          <div className="skeleton" style={{ height: 70, width: "100%" }} />
        </div>
      )}

      {pitches && pitches.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>History</div>
          <p>No saved pitches yet. Once backend Convex writes land, they will appear here live.</p>
        </div>
      )}

      {pitches && pitches.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {pitches.map((pitch) => (
            <article className="card history-row" key={pitch._id}>
              <div>
                <h2 style={{ fontSize: 18, marginBottom: 4 }}>{pitch.ticker}</h2>
                <p>{pitch.spokenText}</p>
              </div>
              <div className="history-score">{pitch.fitScore.toFixed(1)}</div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
