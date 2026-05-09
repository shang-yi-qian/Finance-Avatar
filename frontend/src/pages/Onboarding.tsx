import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useMutation } from "convex/react";
import { api } from "../../convex/_generated/api";
import { postOnboard } from "../lib/api";
import {
  buildStyleSummary,
  createUserId,
  DEFAULT_USER_PROFILE,
  loadUserProfile,
  saveUserProfile,
  toConvexPortfolio,
  type AssetType,
  type LiveUserProfile,
  type PortfolioHolding,
} from "../lib/userProfile";

const INTERESTS = [
  "semiconductors",
  "AI infrastructure",
  "cloud",
  "consumer tech",
  "crypto",
  "energy",
  "fintech",
  "healthcare",
];
const MAX_RECORDING_SECONDS = 30;

type OnboardResult = Awaited<ReturnType<typeof postOnboard>>;

function newHolding(assetType: AssetType = "stock"): PortfolioHolding {
  return {
    id: `holding-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    ticker: "",
    assetType,
    weight: 0.1,
    avgCost: 0,
  };
}

export default function Onboarding() {
  const upsertUser = useMutation(api.users.upsertUser);
  const initialProfile = useRef<LiveUserProfile>(loadUserProfile()).current;
  const [displayName, setDisplayName] = useState(initialProfile.displayName);
  const [selfieFile, setSelfieFile] = useState<File | null>(null);
  const [selfiePreview, setSelfiePreview] = useState<string | null>(null);
  const [voiceBlob, setVoiceBlob] = useState<Blob | null>(null);
  const [voiceUrl, setVoiceUrl] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(MAX_RECORDING_SECONDS);
  const [riskTolerance, setRiskTolerance] = useState(Math.round(initialProfile.riskTolerance * 100));
  const [jargonLevel, setJargonLevel] = useState(Math.round(initialProfile.jargonLevel * 100));
  const [horizon, setHorizon] = useState(initialProfile.horizon);
  const [experience, setExperience] = useState(initialProfile.experience);
  const [interests, setInterests] = useState<string[]>(initialProfile.thematicInterests);
  const [portfolio, setPortfolio] = useState<PortfolioHolding[]>(initialProfile.portfolio);
  const [result, setResult] = useState<OnboardResult | null>(null);
  const [selectedAvatar, setSelectedAvatar] = useState<string | null>(
    initialProfile.avatarImageUrl ?? null,
  );
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

  const userId = createUserId(displayName);

  useEffect(() => {
    const profile = buildProfile(selectedAvatar ?? undefined, result?.voice_id);
    saveUserProfile(profile);
    if (!profile.displayName || profile.portfolio.length === 0) return;

    const timeout = window.setTimeout(() => {
      upsertUser({
        userId: profile.userId,
        displayName: profile.displayName,
        avatarImageUrl: profile.avatarImageUrl ?? "",
        voiceId: profile.voiceId ?? "pending_voice",
        portfolio: toConvexPortfolio(profile),
        riskTolerance: profile.riskTolerance,
        jargonLevel: profile.jargonLevel,
        horizon: profile.horizon,
        experience: profile.experience,
        thematicInterests: profile.thematicInterests,
        styleProfileSummary: buildStyleSummary(profile),
      }).catch(console.error);
    }, 600);

    return () => window.clearTimeout(timeout);
  }, [displayName, riskTolerance, jargonLevel, horizon, experience, interests, portfolio, selectedAvatar, result, upsertUser]);

  useEffect(() => {
    return () => {
      if (selfiePreview) URL.revokeObjectURL(selfiePreview);
    };
  }, [selfiePreview]);

  useEffect(() => {
    return () => {
      if (voiceUrl) URL.revokeObjectURL(voiceUrl);
    };
  }, [voiceUrl]);

  useEffect(() => {
    return () => {
      stopTracks();
      clearTimer();
    };
  }, []);

  function buildProfile(avatarImageUrl?: string, voiceId?: string): LiveUserProfile {
    return {
      userId,
      displayName: displayName.trim() || DEFAULT_USER_PROFILE.displayName,
      avatarImageUrl,
      voiceId,
      riskTolerance: riskTolerance / 100,
      jargonLevel: jargonLevel / 100,
      horizon,
      experience,
      thematicInterests: interests,
      portfolio: portfolio
        .map((holding) => ({
          ...holding,
          ticker: holding.ticker.trim().toUpperCase(),
          weight: Number.isFinite(holding.weight) ? holding.weight : 0,
          avgCost: Number.isFinite(holding.avgCost) ? holding.avgCost : 0,
        }))
        .filter((holding) => holding.ticker),
    };
  }

  function clearTimer() {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  function stopTracks() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function handleSelfie(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setSelfieFile(file);
    setResult(null);
    if (selfiePreview) URL.revokeObjectURL(selfiePreview);
    setSelfiePreview(file ? URL.createObjectURL(file) : null);
  }

  async function startRecording() {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser does not expose microphone recording.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      streamRef.current = stream;
      recorderRef.current = recorder;
      chunksRef.current = [];
      setVoiceBlob(null);
      if (voiceUrl) {
        URL.revokeObjectURL(voiceUrl);
        setVoiceUrl(null);
      }

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        setVoiceBlob(blob);
        setVoiceUrl(URL.createObjectURL(blob));
        setIsRecording(false);
        clearTimer();
        stopTracks();
      };

      setSecondsLeft(MAX_RECORDING_SECONDS);
      recorder.start();
      setIsRecording(true);
      timerRef.current = window.setInterval(() => {
        setSecondsLeft((current) => {
          if (current <= 1) {
            stopRecording();
            return 0;
          }
          return current - 1;
        });
      }, 1000);
    } catch {
      setError("Microphone permission was blocked or unavailable.");
      stopTracks();
      clearTimer();
      setIsRecording(false);
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    } else {
      setIsRecording(false);
      clearTimer();
      stopTracks();
    }
  }

  function toggleInterest(interest: string) {
    setInterests((current) =>
      current.includes(interest)
        ? current.filter((item) => item !== interest)
        : [...current, interest],
    );
  }

  function updateHolding(id: string, patch: Partial<PortfolioHolding>) {
    setPortfolio((current) =>
      current.map((holding) => (holding.id === id ? { ...holding, ...patch } : holding)),
    );
  }

  function removeHolding(id: string) {
    setPortfolio((current) => current.filter((holding) => holding.id !== id));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setStatus("Generating avatar variants and registering the voice profile...");
    setResult(null);

    const liveProfile = buildProfile(selectedAvatar ?? undefined, result?.voice_id);
    const formData = new FormData();
    if (selfieFile) formData.append("selfie", selfieFile);
    if (voiceBlob) formData.append("voice_recording", voiceBlob, `${liveProfile.userId}-voice.webm`);
    formData.append(
      "quiz_answers",
      JSON.stringify({
        user_id: liveProfile.userId,
        display_name: liveProfile.displayName,
        risk_tolerance: liveProfile.riskTolerance,
        horizon: liveProfile.horizon,
        experience: liveProfile.experience,
        thematic_interests: liveProfile.thematicInterests,
        jargon_level: liveProfile.jargonLevel,
        portfolio: liveProfile.portfolio,
      }),
    );

    try {
      const response = await postOnboard(formData);
      setResult(response);
      setSelectedAvatar(response.avatar_variants[0] ?? selectedAvatar);
      setStatus("Choose the avatar variant for this profile.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Onboarding failed");
      setStatus(null);
    }
  }

  async function saveSelectedAvatar() {
    if (!selectedAvatar || !result) return;
    setError(null);
    setStatus("Saving profile to Convex...");
    const profile = buildProfile(selectedAvatar, result.voice_id);

    try {
      await upsertUser({
        userId: profile.userId,
        displayName: profile.displayName,
        avatarImageUrl: selectedAvatar,
        voiceId: result.voice_id,
        portfolio: toConvexPortfolio(profile),
        riskTolerance: profile.riskTolerance,
        jargonLevel: profile.jargonLevel,
        horizon: profile.horizon,
        experience: profile.experience,
        thematicInterests: profile.thematicInterests,
        styleProfileSummary: buildStyleSummary(profile),
      });
      saveUserProfile(profile);
      setStatus("Profile is ready on the dashboard.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save to Convex");
      setStatus(null);
    }
  }

  const validPortfolio = buildProfile().portfolio.length > 0;
  const canSubmit = Boolean(displayName.trim()) && interests.length > 0 && validPortfolio && !isRecording;

  return (
    <div className="page-stack">
      <header className="page-heading">
        <div>
          <h1>Build investor profile</h1>
          <p style={{ color: "var(--text-dim)" }}>
            Live profile inputs are saved and used by the next pitch request.
          </p>
        </div>
      </header>

    <div className="onboarding-grid">
      <form className="card onboarding-card" onSubmit={handleSubmit}>

        <section className="onboarding-section profile-intro-grid">
          <div className="upload-preview">
            {selfiePreview ? <img src={selfiePreview} alt="Selfie preview" /> : <span>Selfie</span>}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <label className="field-label" htmlFor="display-name">Display name</label>
            <input
              id="display-name"
              className="field-control"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
            <label className="file-button">
              <input type="file" accept="image/*" onChange={handleSelfie} />
              Upload selfie
            </label>
          </div>
        </section>

        <section className="onboarding-section">
          <div className="section-header">
            <div>
              <h2>Voice sample</h2>
              <p>
                Record up to 30 seconds for the voice profile.
              </p>
            </div>
            <button type="button" className={isRecording ? "btn btn-ghost" : "btn btn-primary"} onClick={isRecording ? stopRecording : startRecording}>
              {isRecording ? `Stop ${secondsLeft}s` : "Record"}
            </button>
          </div>
          {voiceUrl ? <audio controls src={voiceUrl} style={{ width: "100%" }} /> : <div className="empty-strip">No voice sample recorded yet.</div>}
        </section>

        <section className="control-grid">
          <label className="field-stack">
            <span>Risk tolerance: {riskTolerance}%</span>
            <input type="range" min="10" max="100" value={riskTolerance} onChange={(event) => setRiskTolerance(Number(event.target.value))} />
          </label>
          <label className="field-stack">
            <span>Jargon tolerance: {jargonLevel}%</span>
            <input type="range" min="10" max="100" value={jargonLevel} onChange={(event) => setJargonLevel(Number(event.target.value))} />
          </label>
          <label className="field-stack">
            <span>Horizon</span>
            <select className="field-control" value={horizon} onChange={(event) => setHorizon(event.target.value)}>
              <option value="3_to_6_months">3 to 6 months</option>
              <option value="6_months_to_2_years">6 months to 2 years</option>
              <option value="2_to_5_years">2 to 5 years</option>
            </select>
          </label>
          <label className="field-stack">
            <span>Experience</span>
            <select className="field-control" value={experience} onChange={(event) => setExperience(event.target.value)}>
              <option value="newer">Newer investor</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </label>
        </section>

        <section className="onboarding-section">
          <div className="section-header">
            <div>
              <h2>Portfolio</h2>
              <p>Add the judge's holdings and asset type. These values are used in pitch scoring.</p>
            </div>
            <button className="btn btn-ghost" type="button" onClick={() => setPortfolio((current) => [...current, newHolding()])}>
              Add holding
            </button>
          </div>
          <div className="portfolio-editor">
            <div className="portfolio-label-row" aria-hidden="true">
              <span>Type</span>
              <span>Ticker</span>
              <span>Weight %</span>
              <span>Avg cost</span>
              <span></span>
            </div>
            {portfolio.map((holding) => (
              <div className="portfolio-row" key={holding.id}>
                <select
                  className="field-control"
                  value={holding.assetType}
                  onChange={(event) => updateHolding(holding.id, { assetType: event.target.value as AssetType })}
                  aria-label="Asset type"
                >
                  <option value="stock">Stock</option>
                  <option value="etf">ETF</option>
                  <option value="crypto">Crypto</option>
                </select>
                <input
                  className="field-control"
                  value={holding.ticker}
                  onChange={(event) => updateHolding(holding.id, { ticker: event.target.value.toUpperCase() })}
                  placeholder={holding.assetType === "crypto" ? "BTC" : "NVDA"}
                  aria-label="Ticker"
                />
                <input
                  className="field-control"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  value={Math.round(holding.weight * 100)}
                  onChange={(event) => updateHolding(holding.id, { weight: Number(event.target.value) / 100 })}
                  aria-label="Portfolio weight percent"
                />
                <input
                  className="field-control"
                  type="number"
                  min="0"
                  step="0.01"
                  value={holding.avgCost}
                  onChange={(event) => updateHolding(holding.id, { avgCost: Number(event.target.value) })}
                  aria-label="Average cost"
                />
                <button className="btn btn-ghost compact-button" type="button" onClick={() => removeHolding(holding.id)}>
                  Remove
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="onboarding-section">
          <div className="section-header">
            <div>
              <h2>Themes</h2>
              <p>Choose the sectors and asset themes the pitch should care about.</p>
            </div>
          </div>
          <div className="segmented-wrap">
            {INTERESTS.map((interest) => (
              <button
                key={interest}
                type="button"
                className={interests.includes(interest) ? "segment active" : "segment"}
                onClick={() => toggleInterest(interest)}
              >
                {interest}
              </button>
            ))}
          </div>
        </section>

        <div className="form-actions">
          <button className="btn btn-primary" type="submit" disabled={!canSubmit}>
            Generate variants
          </button>
          {status && <span className="status-text">{status}</span>}
        </div>
        {error && <p className="error-text">{error}</p>}
      </form>

      <aside className="card variants-panel">
        <div className="section-header">
          <div>
            <h2>Avatar variants</h2>
            <p>Select the version to use on the dashboard.</p>
          </div>
        </div>
        {result ? (
          <>
            <div className="avatar-choice-grid">
              {result.avatar_variants.map((url, index) => (
                <button
                  key={url}
                  type="button"
                  className={selectedAvatar === url ? "avatar-choice selected" : "avatar-choice"}
                  onClick={() => setSelectedAvatar(url)}
                  aria-label={`Choose avatar variant ${index + 1}`}
                >
                  <img src={url} alt={`Avatar variant ${index + 1}`} />
                </button>
              ))}
            </div>
            <button className="btn btn-primary" type="button" onClick={saveSelectedAvatar} disabled={!selectedAvatar}>
              Save selected
            </button>
          </>
        ) : (
          <div className="empty-strip">Variants appear after generation.</div>
        )}
      </aside>
    </div>
    </div>
  );
}
