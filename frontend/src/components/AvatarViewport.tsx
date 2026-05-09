import { useEffect, useRef, useState, type CSSProperties } from "react";

// Phase 4: show avatar image + lipsync video, auto-play audio.
// Priority: videoUrl, then audioUrl with static avatar, then local placeholder.

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
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const meterFrameRef = useRef<number | null>(null);
  const [imageFailed, setImageFailed] = useState(false);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [voiceLevel, setVoiceLevel] = useState(0);
  const showImage = Boolean(avatarImageUrl && !imageFailed);
  const active = isPlaying || (speaking && Boolean(videoUrl));
  const avatarStyle = {
    "--voice-level": voiceLevel.toFixed(3),
    "--avatar-scale": `${1.005 + voiceLevel * 0.035}`,
    "--avatar-y": `${-voiceLevel * 8}px`,
    "--avatar-tilt-x": `${voiceLevel * -2.2}deg`,
    "--avatar-tilt-y": `${voiceLevel * 2.6}deg`,
    "--avatar-brightness": `${1.02 + voiceLevel * 0.14}`,
    "--avatar-saturation": `${1.04 + voiceLevel * 0.22}`,
  } as CSSProperties;

  useEffect(() => {
    setImageFailed(false);
  }, [avatarImageUrl]);

  useEffect(() => {
    return () => {
      stopVoiceMeter();
      sourceRef.current?.disconnect();
      analyserRef.current?.disconnect();
      audioContextRef.current?.close().catch(() => undefined);
    };
  }, []);

  useEffect(() => {
    setAudioBlocked(false);
    setIsPlaying(false);
    setVoiceLevel(0);
    stopVoiceMeter();

    if (!audioUrl || videoUrl || !audioRef.current) return;

    const audio = audioRef.current;
    audio.currentTime = 0;
    const playAttempt = audio.play();
    if (playAttempt) {
      playAttempt.catch(() => {
        setAudioBlocked(true);
        setIsPlaying(false);
      });
    }
  }, [audioUrl, videoUrl]);

  function stopVoiceMeter() {
    if (meterFrameRef.current) {
      window.cancelAnimationFrame(meterFrameRef.current);
      meterFrameRef.current = null;
    }
    setVoiceLevel(0);
  }

  function startVoiceMeter() {
    const audio = audioRef.current;
    if (!audio) return;

    try {
      const AudioContextClass =
        window.AudioContext ||
        (window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextClass) return;

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContextClass();
      }
      if (audioContextRef.current.state === "suspended") {
        audioContextRef.current.resume().catch(() => undefined);
      }
      if (!analyserRef.current) {
        const analyser = audioContextRef.current.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.72;
        analyserRef.current = analyser;
      }
      if (!sourceRef.current) {
        sourceRef.current = audioContextRef.current.createMediaElementSource(audio);
        sourceRef.current.connect(analyserRef.current);
        analyserRef.current.connect(audioContextRef.current.destination);
      }

      const analyser = analyserRef.current;
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (const value of data) {
          sum += Math.abs(value - 128) / 128;
        }
        setVoiceLevel(Math.min(1, sum / data.length * 5.5));
        meterFrameRef.current = window.requestAnimationFrame(tick);
      };
      tick();
    } catch {
      setVoiceLevel(0.55);
    }
  }

  function replayAudio() {
    if (!audioRef.current) return;
    setAudioBlocked(false);
    audioRef.current.currentTime = 0;
    audioRef.current.play().catch(() => {
      setAudioBlocked(true);
    });
  }

  return (
    <div
      className={active ? "avatar-viewport avatar-glow avatar-speaking" : "avatar-viewport"}
      style={avatarStyle}
    >
      {videoUrl ? (
        <video
          className="avatar-media"
          src={videoUrl}
          autoPlay
          controls
          playsInline
          onPlay={() => {
            setIsPlaying(true);
            setVoiceLevel(0.55);
          }}
          onPause={() => {
            setIsPlaying(false);
            setVoiceLevel(0);
          }}
          onEnded={() => {
            setIsPlaying(false);
            setVoiceLevel(0);
          }}
        />
      ) : (
        <>
          {showImage ? (
            <img
              className="avatar-media"
              src={avatarImageUrl}
              alt="Your PitchSnap avatar"
              onError={() => setImageFailed(true)}
            />
          ) : (
            <div className="avatar-art-fallback">
              <span>PitchSnap</span>
            </div>
          )}
          {audioUrl && (
            <>
              <audio
                ref={audioRef}
                src={audioUrl}
                autoPlay
                crossOrigin="anonymous"
                onPlay={() => {
                  setAudioBlocked(false);
                  setIsPlaying(true);
                  startVoiceMeter();
                }}
                onPause={() => {
                  setIsPlaying(false);
                  stopVoiceMeter();
                }}
                onEnded={() => {
                  setIsPlaying(false);
                  stopVoiceMeter();
                }}
              />
              <div className="avatar-playback-bar">
                <span>{isPlaying ? "Speaking" : audioBlocked ? "Tap to play" : "Pitch audio ready"}</span>
                <button className="avatar-playback-button" type="button" onClick={replayAudio}>
                  {isPlaying ? "Restart" : "Play"}
                </button>
              </div>
            </>
          )}
        </>
      )}

      {!showImage && !videoUrl && !audioUrl && (
        <div className="avatar-placeholder">
          <span>Complete onboarding to generate your avatar</span>
        </div>
      )}
    </div>
  );
}
