import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import TickerInput from "../components/TickerInput";
import PitchCard from "../components/PitchCard";
import FeedbackButtons from "../components/FeedbackButtons";
import StyleProfilePanel from "../components/StyleProfilePanel";
import RealtimeVoiceToggle from "../components/RealtimeVoiceToggle";
import { postPitch, type FeedbackResponse, type PitchResponse } from "../lib/api";
import {
  applyBackendProfileToLocal,
  loadUserProfile,
  saveUserProfile,
  toBackendProfile,
} from "../lib/userProfile";

export default function Dashboard() {
  const [activeProfile, setActiveProfile] = useState(() => loadUserProfile());
  const [pitch, setPitch] = useState<PitchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profileRefresh, setProfileRefresh] = useState(0);
  const convexUser = useQuery(api.users.getUser, { userId: activeProfile.userId });

  async function handleTicker(ticker: string) {
    const latestProfile = loadUserProfile();
    const profileForPitch = {
      ...latestProfile,
      voiceId: latestProfile.voiceId || convexUser?.voiceId,
    };
    setActiveProfile(profileForPitch);
    setLoading(true);
    setError(null);
    setPitch(null);
    try {
      const result = await postPitch(ticker, profileForPitch.userId, toBackendProfile(profileForPitch));
      setPitch(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function handleFeedback(_signal: string, response: FeedbackResponse) {
    const latestProfile = loadUserProfile();
    const updated = applyBackendProfileToLocal(latestProfile, response.profile);
    saveUserProfile(updated);
    setActiveProfile(updated);
    setProfileRefresh((n) => n + 1);
  }

  return (
    <div className="page-stack">
      <header className="page-heading">
        <div>
          <h1>Stock Pitch Studio</h1>
          <p>
            Type a ticker and get a live research report, portfolio-fit score, and jargon-adapted pitch.
            If onboarding created a voice clone, the pitch also plays as audio.
          </p>
        </div>
      </header>

      <div className="report-dashboard-grid">
      <aside className="report-sidebar">
        <StyleProfilePanel userId={activeProfile.userId} refreshKey={profileRefresh} />
        <div className="card mini-profile-card">
          <span className="profile-label">Portfolio snapshot</span>
          <strong>{activeProfile.displayName}</strong>
          <p>{activeProfile.portfolio.map((holding) => `${holding.ticker} ${Math.round(holding.weight * 100)}%`).join(" · ")}</p>
          {convexUser?.voiceId || activeProfile.voiceId ? (
            <span className="voice-status voice-status-live">Voice ready</span>
          ) : (
            <span className="voice-status">Voice optional</span>
          )}
        </div>
        {pitch && <RealtimeVoiceToggle ticker={pitch.ticker} />}
      </aside>

      <div className="content-column">
        <TickerInput onSubmit={handleTicker} loading={loading} />

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        {loading && (
          <div className="card page-stack">
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
              ticker={pitch.ticker}
              userId={activeProfile.userId}
              profileSnapshot={toBackendProfile(activeProfile)}
              onFeedback={handleFeedback}
            />
          </>
        )}

        {!pitch && !loading && (
          <div className="card empty-state">
            <p>Enter a ticker to get your personalised pitch</p>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
