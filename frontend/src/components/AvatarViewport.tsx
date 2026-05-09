// Phase 4: show avatar image + lipsync video, auto-play audio
// Priority: videoUrl (MP4 lipsync) → audioUrl (TTS + static image) → static placeholder

interface Props {
  avatarImageUrl?: string;
  audioUrl?: string;
  videoUrl?: string;
  speaking?: boolean;
}

export default function AvatarViewport({
  avatarImageUrl,
  audioUrl,
  videoUrl,
  speaking = false,
}: Props) {
  const placeholder =
    "https://placehold.co/320x320/1a1a2e/7c3aed?text=Avatar";

  return (
    <div
      style={{
        width: 320,
        height: 320,
        borderRadius: 16,
        overflow: "hidden",
        position: "relative",
        background: "linear-gradient(135deg, #1a1a2e 0%, #0d0d14 100%)",
        border: "1px solid var(--border)",
      }}
      className={speaking ? "avatar-glow" : ""}
    >
      {videoUrl ? (
        <video
          src={videoUrl}
          autoPlay
          loop
          playsInline
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : (
        <>
          <img
            src={avatarImageUrl ?? placeholder}
            alt="Your PitchSnap avatar"
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
          {audioUrl && (
            <audio src={audioUrl} autoPlay style={{ display: "none" }} />
          )}
        </>
      )}

      {/* Phase 4 placeholder overlay */}
      {!avatarImageUrl && !videoUrl && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexDirection: "column",
            gap: 8,
            color: "var(--text-dim)",
            fontSize: 13,
          }}
        >
          <span style={{ fontSize: 32 }}>👤</span>
          <span>Complete onboarding to generate your avatar</span>
        </div>
      )}
    </div>
  );
}
