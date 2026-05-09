import { useState } from "react";
import TickerInput from "../components/TickerInput";
import PitchCard from "../components/PitchCard";
import AvatarViewport from "../components/AvatarViewport";
import FeedbackButtons from "../components/FeedbackButtons";
import StyleProfilePanel from "../components/StyleProfilePanel";
import RealtimeVoiceToggle from "../components/RealtimeVoiceToggle";
import { postPitch, type PitchResponse } from "../lib/api";

const USER_ID = "kai_demo";

export default function Dashboard() {
  const [pitch, setPitch] = useState<PitchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profileRefresh, setProfileRefresh] = useState(0);

  async function handleTicker(ticker: string) {
    setLoading(true);
    setError(null);
    setPitch(null);
    try {
      const result = await postPitch(ticker, USER_ID);
      setPitch(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function handleFeedback() {
    setProfileRefresh((n) => n + 1);
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 24, alignItems: "start" }}>
      {/* Left column */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <AvatarViewport
          audioUrl={pitch?.audio_url ?? undefined}
          videoUrl={pitch?.video_url ?? undefined}
          speaking={!!pitch?.audio_url}
        />
        <StyleProfilePanel userId={USER_ID} refreshKey={profileRefresh} />
        {pitch && <RealtimeVoiceToggle ticker={pitch.ticker} />}
      </div>

      {/* Right column */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <TickerInput onSubmit={handleTicker} loading={loading} />

        {error && (
          <div
            style={{
              padding: 16,
              borderRadius: 8,
              background: "rgba(239,68,68,0.1)",
              border: "1px solid rgba(239,68,68,0.3)",
              color: "var(--red)",
            }}
          >
            {error}
          </div>
        )}

        {loading && (
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="skeleton" style={{ height: 24, width: "30%" }} />
            <div className="skeleton" style={{ height: 60, width: "100%" }} />
            <div className="skeleton" style={{ height: 14, width: "100%" }} />
            <div className="skeleton" style={{ height: 14, width: "100%" }} />
            <div className="skeleton" style={{ height: 14, width: "80%" }} />
          </div>
        )}

        {pitch && !loading && (
          <>
            <PitchCard pitch={pitch} />
            <FeedbackButtons
              pitchId={pitch.pitch_id}
              userId={USER_ID}
              onFeedback={handleFeedback}
            />
          </>
        )}

        {!pitch && !loading && (
          <div
            className="card"
            style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}
          >
            <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
            <p>Enter a ticker to get your personalised pitch</p>
          </div>
        )}
      </div>
    </div>
  );
}
