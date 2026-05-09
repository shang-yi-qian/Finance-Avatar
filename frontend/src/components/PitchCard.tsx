import type { PitchResponse } from "../lib/api";

interface Props {
  pitch: PitchResponse;
}

const SCORE_LABELS: Record<string, string> = {
  risk_fit: "Risk Fit",
  style_fit: "Style Fit",
  horizon_fit: "Horizon Fit",
  conviction: "Conviction",
};

function ScoreBar({ score }: { score: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div className="score-bar-track" style={{ flex: 1 }}>
        <div
          className="score-bar-fill"
          style={{ width: `${(score / 10) * 100}%` }}
        />
      </div>
      <span style={{ color: "var(--accent-light)", fontWeight: 600, minWidth: 32, textAlign: "right" }}>
        {score.toFixed(1)}
      </span>
    </div>
  );
}

export default function PitchCard({ pitch }: Props) {
  const totalColor =
    pitch.fit_score.total >= 8
      ? "var(--green)"
      : pitch.fit_score.total >= 6
      ? "var(--yellow)"
      : "var(--red)";

  return (
    <div className="card" id={`pitch-${pitch.pitch_id ?? pitch.ticker}`}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 28, color: "var(--text-bright)" }}>{pitch.ticker}</h2>
          <span style={{ color: "var(--text-dim)", fontSize: 13 }}>Fit analysis</span>
        </div>
        <div
          style={{
            fontSize: 40,
            fontWeight: 700,
            color: totalColor,
            lineHeight: 1,
          }}
        >
          {pitch.fit_score.total.toFixed(1)}
          <span style={{ fontSize: 16, color: "var(--text-dim)", fontWeight: 400 }}>/10</span>
        </div>
      </div>

      {/* Spoken pitch */}
      <p
        style={{
          background: "var(--bg-input)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: "16px",
          marginBottom: 20,
          fontStyle: "italic",
          lineHeight: 1.6,
          color: "var(--text-bright)",
        }}
      >
        "{pitch.spoken_text}"
      </p>

      {/* Score breakdown */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {Object.entries(pitch.fit_score.breakdown).map(([key, val]) => (
          <div key={key}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontSize: 13, color: "var(--text-dim)" }}>
                {SCORE_LABELS[key] ?? key}
              </span>
              <span style={{ fontSize: 12, color: "var(--text-dim)", maxWidth: "60%", textAlign: "right" }}>
                {val.reason}
              </span>
            </div>
            <ScoreBar score={val.score} />
          </div>
        ))}
      </div>
    </div>
  );
}
