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
    <div className={speaking ? "avatar-viewport avatar-glow" : "avatar-viewport"}>
      {videoUrl ? (
        <video
          src={videoUrl}
          autoPlay
          loop
          playsInline
        />
      ) : (
        <>
          <img
            src={avatarImageUrl ?? placeholder}
            alt="Your PitchSnap avatar"
          />
          {audioUrl && (
            <audio src={audioUrl} autoPlay style={{ display: "none" }} />
          )}
        </>
      )}

      {/* Phase 4 placeholder overlay */}
      {!avatarImageUrl && !videoUrl && (
        <div className="avatar-placeholder">
          <span>Complete onboarding to generate your avatar</span>
        </div>
      )}
    </div>
  );
}
