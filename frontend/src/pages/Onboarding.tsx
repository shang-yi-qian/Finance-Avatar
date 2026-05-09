import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useMutation } from "convex/react";
import { api } from "../../convex/_generated/api";
import { onboardProgressUrl, postOnboard, resolveMediaUrl, type OnboardProgressEvent } from "../lib/api";
import {
  buildStyleSummary,
  createUserId,
  DEFAULT_USER_PROFILE,
  loadUserProfile,
  saveUserProfile,
  TALKING_VIDEO_KEY,
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
const FACE_RECORDING_SECONDS = 6;
const DEFAULT_RECORDING_PROMPT =
  "Tell me about one stock, ETF, or crypto you like. Why does it fit your style?";
const RECORDING_PROMPTS = [
  {
    id: "favorite-asset",
    label: "Favorite asset",
    prompt: DEFAULT_RECORDING_PROMPT,
  },
  {
    id: "avoid-list",
    label: "Avoid list",
    prompt: "Tell me about an investment you would avoid. What makes it feel wrong for you?",
  },
  {
    id: "risk-style",
    label: "Risk style",
    prompt: "Explain how you think about risk to a friend who is newer to investing.",
  },
  {
    id: "portfolio-taste",
    label: "Portfolio taste",
    prompt: "Describe your ideal portfolio. What themes, sectors, or asset types do you want more of?",
  },
  {
    id: "market-reaction",
    label: "Market reaction",
    prompt: "Talk through a recent market move you noticed. What did you think it meant?",
  },
  {
    id: "casual-pitch",
    label: "Casual pitch",
    prompt: "Pick any ticker or crypto you know and pitch it in your normal speaking style.",
  },
];

type OnboardResult = Awaited<ReturnType<typeof postOnboard>>;
type StoredMedia = {
  dataUrl: string;
  name: string;
  type: string;
  savedAt: number;
};

const STORED_SELFIE_KEY = "pitchsnap:onboardingSelfie";
const STORED_VOICE_KEY = "pitchsnap:onboardingVoice";
const STORED_ONBOARD_RESULT_KEY = "pitchsnap:onboardingResult";

function newHolding(assetType: AssetType = "stock"): PortfolioHolding {
  return {
    id: `holding-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    ticker: "",
    assetType,
    weight: 0.1,
    avgCost: 0,
  };
}

function createOnboardJobId() {
  if (typeof window !== "undefined" && window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `onboard-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function loadStoredMedia(key: string): StoredMedia | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) || "null") as StoredMedia | null;
    if (!parsed?.dataUrl || !parsed.name || !parsed.type) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveStoredMedia(key: string, media: StoredMedia) {
  try {
    window.localStorage.setItem(key, JSON.stringify(media));
  } catch {
    // Browser storage can reject larger voice clips; the in-memory preview still works.
  }
}

function clearStoredOnboardResult() {
  try {
    window.localStorage.removeItem(STORED_ONBOARD_RESULT_KEY);
  } catch {
    // Ignore storage errors; the current in-memory result will still reset.
  }
}

function loadStoredOnboardResult(): OnboardResult | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORED_ONBOARD_RESULT_KEY) || "null") as OnboardResult | null;
    if (!Array.isArray(parsed?.avatar_variants)) return null;
    return {
      ...parsed,
      avatar_variants: parsed.avatar_variants.map((url) => resolveMediaUrl(url) ?? url),
    };
  } catch {
    return null;
  }
}

function saveStoredOnboardResult(result: OnboardResult) {
  try {
    window.localStorage.setItem(STORED_ONBOARD_RESULT_KEY, JSON.stringify(result));
  } catch {
    // Ignore storage errors; Convex/local profile still store the selected avatar.
  }
}

function dataUrlToBlob(dataUrl: string): Blob {
  const [meta, base64] = dataUrl.split(",");
  const mime = meta.match(/data:(.*?);base64/)?.[1] || "application/octet-stream";
  const binary = window.atob(base64 || "");
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: mime });
}

function storedMediaToFile(media: StoredMedia): File {
  return new File([dataUrlToBlob(media.dataUrl)], media.name, { type: media.type });
}

function readAsDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function waitForVideoEvent(video: HTMLVideoElement, eventName: keyof HTMLVideoElementEventMap): Promise<void> {
  return new Promise((resolve, reject) => {
    const onEvent = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error(`Video ${eventName} failed`));
    };
    const cleanup = () => {
      video.removeEventListener(eventName, onEvent);
      video.removeEventListener("error", onError);
    };
    video.addEventListener(eventName, onEvent, { once: true });
    video.addEventListener("error", onError, { once: true });
  });
}

async function extractFaceReferenceFrames(videoUrl: string, userId: string): Promise<File[]> {
  if (!videoUrl) return [];

  const video = document.createElement("video");
  video.src = videoUrl;
  video.muted = true;
  video.playsInline = true;
  video.preload = "metadata";
  video.load();

  try {
    if (video.readyState < 1) {
      await waitForVideoEvent(video, "loadedmetadata");
    }

    const duration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : FACE_RECORDING_SECONDS;
    const times = [duration * 0.18, duration * 0.5, duration * 0.82];
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 1024;
    const context = canvas.getContext("2d");
    if (!context || video.videoWidth === 0 || video.videoHeight === 0) return [];

    const frames: File[] = [];
    for (const [index, time] of times.entries()) {
      video.currentTime = Math.max(0, Math.min(duration - 0.05, time));
      await waitForVideoEvent(video, "seeked");

      const sourceSize = Math.min(video.videoWidth, video.videoHeight);
      const sourceX = (video.videoWidth - sourceSize) / 2;
      const sourceY = (video.videoHeight - sourceSize) / 2;
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.drawImage(video, sourceX, sourceY, sourceSize, sourceSize, 0, 0, canvas.width, canvas.height);

      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
      if (blob) {
        frames.push(new File([blob], `${userId}-motion-reference-${index + 1}.jpg`, { type: "image/jpeg" }));
      }
    }
    return frames;
  } catch {
    return [];
  }
}

export default function Onboarding() {
  const upsertUser = useMutation(api.users.upsertUser);
  const initialProfile = useRef<LiveUserProfile>(loadUserProfile()).current;
  const initialSelfieMedia = useRef<StoredMedia | null>(loadStoredMedia(STORED_SELFIE_KEY)).current;
  const initialVoiceMedia = useRef<StoredMedia | null>(loadStoredMedia(STORED_VOICE_KEY)).current;
  const initialFaceVideoMedia = useRef<StoredMedia | null>(loadStoredMedia(TALKING_VIDEO_KEY)).current;
  const initialOnboardResult = useRef<OnboardResult | null>(loadStoredOnboardResult()).current;
  const initialVoicePrompt = initialProfile.voicePrompt || DEFAULT_RECORDING_PROMPT;
  const [displayName, setDisplayName] = useState(initialProfile.displayName);
  const [selfieFile, setSelfieFile] = useState<File | null>(() =>
    initialSelfieMedia ? storedMediaToFile(initialSelfieMedia) : null,
  );
  const [selfiePreview, setSelfiePreview] = useState<string | null>(initialSelfieMedia?.dataUrl ?? null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [voiceBlob, setVoiceBlob] = useState<Blob | null>(() =>
    initialVoiceMedia ? dataUrlToBlob(initialVoiceMedia.dataUrl) : null,
  );
  const [voiceUrl, setVoiceUrl] = useState<string | null>(initialVoiceMedia?.dataUrl ?? null);
  const [voiceFileName, setVoiceFileName] = useState(initialVoiceMedia?.name ?? `${createUserId(initialProfile.displayName)}-voice.webm`);
  const [faceVideoUrl, setFaceVideoUrl] = useState<string | null>(initialFaceVideoMedia?.dataUrl ?? null);
  const [isFaceRecording, setIsFaceRecording] = useState(false);
  const [faceSecondsLeft, setFaceSecondsLeft] = useState(FACE_RECORDING_SECONDS);
  const [voicePrompt, setVoicePrompt] = useState(initialVoicePrompt);
  const [selectedPromptId, setSelectedPromptId] = useState(
    RECORDING_PROMPTS.find((option) => option.prompt === initialVoicePrompt)?.id ?? "custom",
  );
  const [voiceTranscript, setVoiceTranscript] = useState(initialProfile.voiceTranscript || "");
  const [slangExamples, setSlangExamples] = useState<string[]>(initialProfile.slangExamples);
  const [preferredPhrases, setPreferredPhrases] = useState<string[]>(initialProfile.preferredPhrases);
  const [toneFormality, setToneFormality] = useState(initialProfile.toneFormality);
  const [isRecording, setIsRecording] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(MAX_RECORDING_SECONDS);
  const [riskTolerance, setRiskTolerance] = useState(Math.round(initialProfile.riskTolerance * 100));
  const [jargonLevel, setJargonLevel] = useState(Math.round(initialProfile.jargonLevel * 100));
  const [horizon, setHorizon] = useState(initialProfile.horizon);
  const [experience, setExperience] = useState(initialProfile.experience);
  const [interests, setInterests] = useState<string[]>(initialProfile.thematicInterests);
  const [portfolio, setPortfolio] = useState<PortfolioHolding[]>(initialProfile.portfolio);
  const [result, setResult] = useState<OnboardResult | null>(initialOnboardResult);
  const [selectedAvatar, setSelectedAvatar] = useState<string | null>(
    initialProfile.avatarImageUrl ?? initialOnboardResult?.avatar_variants[0] ?? null,
  );
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progressEvents, setProgressEvents] = useState<OnboardProgressEvent[]>([]);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const faceRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const cameraVideoRef = useRef<HTMLVideoElement | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const faceChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const faceTimerRef = useRef<number | null>(null);

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
        voicePrompt: profile.voicePrompt,
        voiceTranscript: profile.voiceTranscript,
        slangExamples: profile.slangExamples,
        preferredPhrases: profile.preferredPhrases,
        toneFormality: profile.toneFormality,
        styleProfileSummary: buildStyleSummary(profile),
      }).catch(console.error);
    }, 600);

    return () => window.clearTimeout(timeout);
  }, [
    displayName,
    riskTolerance,
    jargonLevel,
    horizon,
    experience,
    interests,
    portfolio,
    selectedAvatar,
    result,
    voicePrompt,
    voiceTranscript,
    slangExamples,
    preferredPhrases,
    toneFormality,
    upsertUser,
  ]);

  useEffect(() => {
    return () => {
      if (selfiePreview?.startsWith("blob:")) URL.revokeObjectURL(selfiePreview);
    };
  }, [selfiePreview]);

  useEffect(() => {
    return () => {
      if (voiceUrl?.startsWith("blob:")) URL.revokeObjectURL(voiceUrl);
    };
  }, [voiceUrl]);

  useEffect(() => {
    return () => {
      if (faceVideoUrl?.startsWith("blob:")) URL.revokeObjectURL(faceVideoUrl);
    };
  }, [faceVideoUrl]);

  useEffect(() => {
    return () => {
      stopTracks();
      releaseCameraStream();
      clearTimer();
      clearFaceTimer();
    };
  }, []);

  useEffect(() => {
    if (!cameraActive || !cameraVideoRef.current || !cameraStreamRef.current) return;

    cameraVideoRef.current.srcObject = cameraStreamRef.current;
    cameraVideoRef.current.play().catch(() => {
      setCameraError("Camera preview could not start. Try reopening the camera.");
    });
  }, [cameraActive]);

  function buildProfile(avatarImageUrl?: string, voiceId?: string): LiveUserProfile {
    return {
      userId,
      displayName: displayName.trim() || DEFAULT_USER_PROFILE.displayName,
      avatarImageUrl: avatarImageUrl ?? selectedAvatar ?? initialProfile.avatarImageUrl,
      talkingVideoUrl: faceVideoUrl ?? initialProfile.talkingVideoUrl,
      voiceId: voiceId ?? result?.voice_id ?? initialProfile.voiceId,
      voicePrompt,
      voiceTranscript,
      slangExamples,
      preferredPhrases,
      toneFormality,
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

  function clearFaceTimer() {
    if (faceTimerRef.current) {
      window.clearInterval(faceTimerRef.current);
      faceTimerRef.current = null;
    }
  }

  function stopTracks() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function releaseCameraStream() {
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null;
    if (cameraVideoRef.current) {
      cameraVideoRef.current.srcObject = null;
    }
  }

  async function startCamera() {
    setError(null);
    setCameraError(null);

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("This browser does not expose camera capture.");
      return;
    }

    try {
      releaseCameraStream();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width: { ideal: 1280 },
          height: { ideal: 1280 },
        },
        audio: false,
      });
      cameraStreamRef.current = stream;
      setCameraActive(true);
    } catch {
      setCameraError("Camera permission was blocked or unavailable.");
      releaseCameraStream();
      setCameraActive(false);
    }
  }

  function stopCamera() {
    releaseCameraStream();
    setCameraActive(false);
  }

  function getSupportedVideoMimeType() {
    const candidates = ["video/webm;codecs=vp8", "video/webm", "video/mp4"];
    return candidates.find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) || "";
  }

  async function startFaceMotionRecording() {
    setError(null);
    setCameraError(null);

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setCameraError("This browser does not expose video recording.");
      return;
    }

    try {
      releaseCameraStream();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width: { ideal: 480 },
          height: { ideal: 480 },
          frameRate: { ideal: 18, max: 24 },
        },
        audio: false,
      });
      cameraStreamRef.current = stream;
      setCameraActive(true);
      faceChunksRef.current = [];
      setFaceVideoUrl(null);

      const mimeType = getSupportedVideoMimeType();
      const recorder = new MediaRecorder(stream, {
        ...(mimeType ? { mimeType } : {}),
        videoBitsPerSecond: 420_000,
      });
      faceRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) faceChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const type = recorder.mimeType || mimeType || "video/webm";
        const blob = new Blob(faceChunksRef.current, { type });
        readAsDataUrl(blob)
          .then((dataUrl) => {
            setFaceVideoUrl(dataUrl);
            saveStoredMedia(TALKING_VIDEO_KEY, {
              dataUrl,
              name: `${userId}-talking-face.webm`,
              type,
              savedAt: Date.now(),
            });
            setStatus("Face motion sample saved as an extra OpenAI avatar reference.");
          })
          .catch(() => {
            setFaceVideoUrl(URL.createObjectURL(blob));
          });
        setIsFaceRecording(false);
        clearFaceTimer();
        stopCamera();
      };

      recorder.start(250);
      setIsFaceRecording(true);
      setFaceSecondsLeft(FACE_RECORDING_SECONDS);
      faceTimerRef.current = window.setInterval(() => {
        setFaceSecondsLeft((current) => {
          if (current <= 1) {
            stopFaceMotionRecording();
            return 0;
          }
          return current - 1;
        });
      }, 1000);
    } catch {
      setCameraError("Camera permission was blocked or video recording is unavailable.");
      setIsFaceRecording(false);
      clearFaceTimer();
      stopCamera();
    }
  }

  function stopFaceMotionRecording() {
    if (faceRecorderRef.current?.state === "recording") {
      faceRecorderRef.current.stop();
    } else {
      setIsFaceRecording(false);
      clearFaceTimer();
      stopCamera();
    }
  }

  async function setSelfieReference(file: File, statusMessage: string) {
    setSelfieFile(file);
    setResult(null);
    clearStoredOnboardResult();
    const dataUrl = await readAsDataUrl(file);
    setSelfiePreview(dataUrl);
    saveStoredMedia(STORED_SELFIE_KEY, {
      dataUrl,
      name: file.name,
      type: file.type || "image/jpeg",
      savedAt: Date.now(),
    });
    setStatus(statusMessage);
  }

  async function handleSelfie(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (!file) return;
    await setSelfieReference(file, "Uploaded image saved as the avatar reference.");
  }

  async function captureCameraSelfie() {
    const video = cameraVideoRef.current;
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
      setCameraError("Camera is still warming up. Try capture again in a second.");
      return;
    }

    const size = Math.min(video.videoWidth, video.videoHeight);
    const sourceX = (video.videoWidth - size) / 2;
    const sourceY = (video.videoHeight - size) / 2;
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 1024;
    const context = canvas.getContext("2d");
    if (!context) {
      setCameraError("Could not capture from this camera stream.");
      return;
    }

    context.drawImage(video, sourceX, sourceY, size, size, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", 0.92);
    });
    if (!blob) {
      setCameraError("Could not save the captured frame.");
      return;
    }

    const file = new File([blob], `${userId}-camera-reference.jpg`, { type: "image/jpeg" });
    await setSelfieReference(file, "Live camera reference captured and saved locally.");
    setCameraError(null);
    stopCamera();
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
        const fileName = `${userId}-voice.webm`;
        setVoiceFileName(fileName);
        readAsDataUrl(blob)
          .then((dataUrl) => {
            setVoiceUrl(dataUrl);
            saveStoredMedia(STORED_VOICE_KEY, {
              dataUrl,
              name: fileName,
              type: blob.type || "audio/webm",
              savedAt: Date.now(),
            });
          })
          .catch(() => {
            setVoiceUrl(URL.createObjectURL(blob));
          });
        setResult(null);
        clearStoredOnboardResult();
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
    setStatus("Preparing camera image and voice sample upload...");
    setResult(null);
    const jobId = createOnboardJobId();
    const initialProgress: OnboardProgressEvent = {
      stage: "prepare",
      message: "Preparing camera image, voice sample, and profile answers for upload.",
      status: "running",
      timestamp: Date.now() / 1000,
    };
    setProgressEvents([initialProgress]);

    const liveProfile = buildProfile(selectedAvatar ?? undefined, result?.voice_id);
    const formData = new FormData();
    formData.append("job_id", jobId);
    if (selfieFile) formData.append("selfie", selfieFile);
    if (voiceBlob) formData.append("voice_recording", voiceBlob, voiceFileName || `${liveProfile.userId}-voice.webm`);
    if (faceVideoUrl) {
      setStatus("Extracting motion reference frames for OpenAI avatar generation...");
      setProgressEvents((current) => [
        ...current,
        {
          stage: "motion_frames",
          message: "Extracting still frames from the short face-motion clip. These guide the generated avatar; the raw clip is not shown on the dashboard.",
          status: "running",
          timestamp: Date.now() / 1000,
        },
      ]);
      const referenceFrames = await extractFaceReferenceFrames(faceVideoUrl, liveProfile.userId);
      referenceFrames.forEach((frame) => formData.append("face_reference_frames", frame, frame.name));
    }
    formData.append(
      "quiz_answers",
      JSON.stringify({
        job_id: jobId,
        user_id: liveProfile.userId,
        display_name: liveProfile.displayName,
        risk_tolerance: liveProfile.riskTolerance,
        horizon: liveProfile.horizon,
        experience: liveProfile.experience,
        thematic_interests: liveProfile.thematicInterests,
        jargon_level: liveProfile.jargonLevel,
        portfolio: liveProfile.portfolio,
        voice_prompt: voicePrompt,
        voice_id: liveProfile.voiceId,
      }),
    );

    let progressSource: EventSource | null = null;
    if (typeof EventSource !== "undefined") {
      progressSource = new EventSource(onboardProgressUrl(jobId));
      progressSource.onmessage = (message) => {
        try {
          const progress = JSON.parse(message.data) as OnboardProgressEvent;
          setProgressEvents((current) => [...current, progress]);
          setStatus(progress.message);
        } catch {
          setProgressEvents((current) => [
            ...current,
            {
              stage: "progress",
              message: "Received an unreadable progress update from the backend.",
              status: "running",
              timestamp: Date.now() / 1000,
            },
          ]);
        }
      };
      progressSource.onerror = () => {
        setProgressEvents((current) => [
          ...current,
          {
            stage: "progress",
            message: "Progress stream disconnected; waiting for the final onboarding response.",
            status: "running",
            timestamp: Date.now() / 1000,
          },
        ]);
      };
    }

    try {
      const response = await postOnboard(formData);
      const patch = response.style_profile_patch ?? {};
      const nextSlang = patch.slang_examples?.filter(Boolean) ?? slangExamples;
      const nextPhrases = patch.preferred_phrases?.filter(Boolean) ?? preferredPhrases;
      setVoiceTranscript(response.voice_transcript || patch.transcript || "");
      setSlangExamples(nextSlang.length > 0 ? nextSlang : slangExamples);
      setPreferredPhrases(nextPhrases.length > 0 ? nextPhrases : preferredPhrases);
      if (typeof patch.formality === "number") {
        setToneFormality(Math.max(0, Math.min(1, patch.formality)));
      }
      setResult(response);
      saveStoredOnboardResult(response);
      setSelectedAvatar(response.avatar_variants[0] ?? selectedAvatar);
      setStatus("Choose the avatar variant for this profile.");
      setProgressEvents((current) => [
        ...current,
        {
          stage: "complete",
          message: "Frontend received avatar variants and voice profile data.",
          status: "complete",
          timestamp: Date.now() / 1000,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Onboarding failed");
      setStatus(null);
      setProgressEvents((current) => [
        ...current,
        {
          stage: "error",
          message: err instanceof Error ? err.message : "Onboarding failed",
          status: "error",
          timestamp: Date.now() / 1000,
        },
      ]);
    } finally {
      progressSource?.close();
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
        voicePrompt: profile.voicePrompt,
        voiceTranscript: profile.voiceTranscript,
        slangExamples: profile.slangExamples,
        preferredPhrases: profile.preferredPhrases,
        toneFormality: profile.toneFormality,
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
  const canSubmit = Boolean(displayName.trim()) && interests.length > 0 && validPortfolio && !isRecording && !isFaceRecording && !cameraActive;

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
          <div className="upload-preview camera-preview">
            {cameraActive ? (
              <video ref={cameraVideoRef} muted playsInline aria-label="Live camera preview" />
            ) : selfiePreview ? (
              <img src={selfiePreview} alt="Captured camera reference" />
            ) : (
              <span>Camera</span>
            )}
          </div>
          <div className="identity-panel">
            <label className="field-label" htmlFor="display-name">Display name</label>
            <input
              id="display-name"
              className="field-control"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
            <div className="camera-controls">
              <button className={cameraActive ? "btn btn-ghost" : "btn btn-primary"} type="button" onClick={cameraActive ? stopCamera : startCamera}>
                {cameraActive ? "Close camera" : "Open camera"}
              </button>
              <button className="btn btn-ghost" type="button" onClick={captureCameraSelfie} disabled={!cameraActive}>
                Capture
              </button>
              <label className="file-button">
                <input type="file" accept="image/*" onChange={handleSelfie} />
                Upload fallback
              </label>
            </div>
            {selfieFile && <p className="hint-text">Reference captured: {selfieFile.name}</p>}
            {cameraError && <p className="error-text">{cameraError}</p>}
          </div>
        </section>

        <section className="onboarding-section face-motion-section">
          <div className="section-header">
            <div>
              <h2>Motion reference</h2>
              <p>
                Record a short silent clip. Smile, blink, and say a sentence naturally so OpenAI has expression references for the generated avatar.
              </p>
            </div>
            <button
              type="button"
              className={isFaceRecording ? "btn btn-ghost" : "btn btn-primary"}
              onClick={isFaceRecording ? stopFaceMotionRecording : startFaceMotionRecording}
              disabled={isRecording}
            >
              {isFaceRecording ? `Stop ${faceSecondsLeft}s` : "Record motion"}
            </button>
          </div>
          {faceVideoUrl ? (
            <div className="face-motion-preview">
              <video src={faceVideoUrl} muted loop playsInline controls />
              <p>Saved locally as reference frames for avatar generation. The raw clip is not shown on the dashboard.</p>
            </div>
          ) : (
            <div className="empty-strip">No motion reference recorded yet.</div>
          )}
        </section>

        <section className="onboarding-section">
          <div className="section-header">
            <div>
              <h2>Voice sample</h2>
              <p>
                Pick a prompt the judge can answer naturally, then record it so the avatar learns real lingo.
              </p>
            </div>
            <button type="button" className={isRecording ? "btn btn-ghost" : "btn btn-primary"} onClick={isRecording ? stopRecording : startRecording}>
              {isRecording ? `Stop ${secondsLeft}s` : "Record"}
            </button>
          </div>
          <div className="prompt-choice-grid" aria-label="Voice prompt choices">
            {RECORDING_PROMPTS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={selectedPromptId === option.id ? "prompt-choice active" : "prompt-choice"}
                onClick={() => {
                  setSelectedPromptId(option.id);
                  setVoicePrompt(option.prompt);
                }}
              >
                <strong>{option.label}</strong>
                <span>{option.prompt}</span>
              </button>
            ))}
          </div>
          <label className="field-stack">
            <span>{selectedPromptId === "custom" ? "Custom recording prompt" : "Selected recording prompt"}</span>
            <textarea
              className="field-control voice-prompt"
              value={voicePrompt}
              onChange={(event) => {
                setVoicePrompt(event.target.value);
                setSelectedPromptId("custom");
              }}
            />
          </label>
          {voiceUrl ? <audio controls src={voiceUrl} style={{ width: "100%" }} /> : <div className="empty-strip">No voice sample recorded yet.</div>}
          {(voiceTranscript || slangExamples.length > 0) && (
            <div className="lingo-panel">
              {voiceTranscript && (
                <p>
                  <strong>Transcript:</strong> {voiceTranscript}
                </p>
              )}
              <div className="tag-list">
                {slangExamples.map((phrase) => (
                  <span className="tag" key={phrase}>{phrase}</span>
                ))}
              </div>
            </div>
          )}
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
        {progressEvents.length > 0 && (
          <div className="onboard-progress" aria-live="polite">
            {progressEvents.slice(-8).map((progress, index) => (
              <div className={`progress-event ${progress.status}`} key={`${progress.stage}-${progress.timestamp}-${index}`}>
                <span>{progress.stage.replaceAll("_", " ")}</span>
                <p>{progress.message}</p>
              </div>
            ))}
          </div>
        )}
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
                  <img
                    src={url}
                    alt={`Avatar variant ${index + 1}`}
                  />
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
