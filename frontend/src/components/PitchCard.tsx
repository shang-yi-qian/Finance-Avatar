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
      <div className="pitch-card-header">
        <div className="pitch-card-title">
          <h2>{pitch.ticker}</h2>
          <span className="meta-label">Fit analysis</span>
        </div>
        <div className="score-value" style={{ color: totalColor }}>
          {pitch.fit_score.total.toFixed(1)}
          <span>/10</span>
        </div>
      </div>

      <p className="spoken-pitch">
        "{pitch.spoken_text}"
      </p>

      <div className="score-breakdown">
        {Object.entries(pitch.fit_score.breakdown).map(([key, val]) => (
          <div className="score-row" key={key}>
            <div className="score-row-header">
              <span>{SCORE_LABELS[key] ?? key}</span>
              <span className="score-reason">{val.reason}</span>
            </div>
            <ScoreBar score={val.score} />
          </div>
        ))}
      </div>
    </div>
  );
}
