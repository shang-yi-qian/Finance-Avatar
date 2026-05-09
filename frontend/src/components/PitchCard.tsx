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

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "Unknown";
  if (typeof value === "number") return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  if (Array.isArray(value)) return value.length ? value.join(", ") : "Unknown";
  return String(value);
}

export default function PitchCard({ pitch }: Props) {
  const report = pitch.report;
  const snapshot = report?.valuation_snapshot ?? {};
  const metricItems: Array<[string, unknown]> = [
    ["Price", snapshot.price],
    ["Market cap", snapshot.market_cap],
    ["Forward P/E", snapshot.pe_forward],
    ["Beta", snapshot.beta],
    ["3M momentum", snapshot.momentum_3m],
    ["Analyst target", snapshot.analyst_target],
    ["Consensus", snapshot.consensus],
    ["Next EPS est.", snapshot.next_eps_estimate],
  ];
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
          <span className="meta-label">{report?.recommendation ?? "Fit analysis"}</span>
        </div>
        <div className="score-value" style={{ color: totalColor }}>
          {pitch.fit_score.total.toFixed(1)}
          <span>/10</span>
        </div>
      </div>

      {report?.headline && <p className="report-headline">{report.headline}</p>}

      <p className="spoken-pitch">
        "{pitch.spoken_text}"
      </p>

      {pitch.audio_url && (
        <div className="audio-card">
          <div>
            <strong>Voice pitch</strong>
            <span>ElevenLabs voice clone / TTS output</span>
          </div>
          <audio src={pitch.audio_url} controls autoPlay />
        </div>
      )}

      {report && (
        <div className="report-grid">
          <section className="report-section report-section-wide">
            <div className="report-section-header">
              <span>Live Research</span>
              <strong>{report.analyst_tone}</strong>
            </div>
            <p>{report.research_summary}</p>
            <p className="muted-copy">{report.earnings_sentiment}</p>
          </section>

          <section className="report-section">
            <div className="report-section-header">
              <span>Portfolio Context</span>
              <strong>{report.portfolio_context.status}</strong>
            </div>
            <p>{report.portfolio_context.summary}</p>
          </section>

          <section className="report-section">
            <div className="report-section-header">
              <span>Valuation Snapshot</span>
              <strong>{formatValue(snapshot.consensus)}</strong>
            </div>
            <div className="metric-grid">
              {metricItems.map(([label, value]) => (
                <div className="metric-tile" key={label}>
                  <span>{label}</span>
                  <strong>{formatValue(value)}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="report-section">
            <div className="report-section-header">
              <span>Takeaways</span>
              <strong>why it matters</strong>
            </div>
            <ul className="report-list">
              {report.key_takeaways.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>

          <section className="report-section">
            <div className="report-section-header">
              <span>Risks</span>
              <strong>watch-outs</strong>
            </div>
            <ul className="report-list">
              {report.risks.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>

          {report.sources.length > 0 && (
            <section className="report-section report-section-wide">
              <div className="report-section-header">
                <span>Exa Sources</span>
                <strong>{report.sources.length} links</strong>
              </div>
              <div className="source-list">
                {report.sources.map((source) => (
                  <a key={source.url} href={source.url} target="_blank" rel="noreferrer">
                    <span>{source.title}</span>
                    {source.publishedDate && <em>{source.publishedDate.slice(0, 10)}</em>}
                  </a>
                ))}
              </div>
            </section>
          )}
        </div>
      )}

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
