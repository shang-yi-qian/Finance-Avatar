import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import TickerInput from "../components/TickerInput";
import PitchCard from "../components/PitchCard";
import AvatarViewport from "../components/AvatarViewport";
import FeedbackButtons from "../components/FeedbackButtons";
import StyleProfilePanel from "../components/StyleProfilePanel";
import RealtimeVoiceToggle from "../components/RealtimeVoiceToggle";
import { postPitch, type FeedbackResponse, type PitchResponse } from "../lib/api";
import {
  applyBackendProfileToLocal,
  loadUserProfile,
  saveUserProfile,
  SELECTED_AVATAR_KEY,
  toBackendProfile,
} from "../lib/userProfile";

export default function Dashboard() {
  const [activeProfile, setActiveProfile] = useState(() => loadUserProfile());
  const [pitch, setPitch] = useState<PitchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profileRefresh, setProfileRefresh] = useState(0);
  const convexUser = useQuery(api.users.getUser, { userId: activeProfile.userId });
  const savedAvatar =
    convexUser?.avatarImageUrl || activeProfile.avatarImageUrl || window.localStorage.getItem(SELECTED_AVATAR_KEY) || undefined;

  async function handleTicker(ticker: string) {
    const latestProfile = loadUserProfile();
    setActiveProfile(latestProfile);
    setLoading(true);
    setError(null);
    setPitch(null);
    try {
      const result = await postPitch(ticker, latestProfile.userId, toBackendProfile(latestProfile));
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
          <h1>Dashboard</h1>
          <p>Run a stock or crypto pitch against the live profile from onboarding.</p>
        </div>
      </header>

      <div className="dashboard-grid">
      <div className="sidebar-column">
        <AvatarViewport
          avatarImageUrl={savedAvatar}
          audioUrl={pitch?.audio_url ?? undefined}
          videoUrl={pitch?.video_url ?? undefined}
          speaking={!!pitch?.audio_url}
        />
        <StyleProfilePanel userId={activeProfile.userId} refreshKey={profileRefresh} />
        {pitch && <RealtimeVoiceToggle ticker={pitch.ticker} />}
      </div>

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
