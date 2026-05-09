import asyncio
import json
import math
import os
import wave
import tempfile
from pathlib import Path
from typing import Optional

from elevenlabs.client import ElevenLabs

from app.services.storage_service import ensure_generated_dir, public_url, unique_filename


VOICE_CACHE_PATH = ensure_generated_dir("meta") / "voices.json"


def _load_voice_cache() -> dict:
    if not VOICE_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(VOICE_CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def _save_voice_cache(cache: dict) -> None:
    VOICE_CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _client() -> Optional[ElevenLabs]:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return None
    return ElevenLabs(api_key=api_key)


def _timeout(name: str, fallback: float) -> float:
    try:
        return float(os.getenv(name, str(fallback)))
    except ValueError:
        return fallback


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_explicit_false(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"0", "false", "no", "off"}


def _cache_voice(user_id: str, voice_id: str) -> str:
    cache = _load_voice_cache()
    cache[user_id] = voice_id
    _save_voice_cache(cache)
    return voice_id


async def clone_voice_once(
    user_id: str,
    audio_bytes: Optional[bytes],
    filename: str,
    existing_voice_id: Optional[str] = None,
) -> str:
    cache = _load_voice_cache()
    if existing_voice_id and not existing_voice_id.startswith("mock_voice_"):
        return _cache_voice(user_id, existing_voice_id)

    cached_voice_id = cache.get(user_id)
    if cached_voice_id and not cached_voice_id.startswith("mock_voice_"):
        return cached_voice_id
    if cached_voice_id and cached_voice_id.startswith("mock_voice_") and not audio_bytes:
        return cache[user_id]

    if not audio_bytes:
        return _cache_voice(user_id, f"mock_voice_{user_id}")

    client = _client()
    if client is None:
        return _cache_voice(user_id, f"mock_voice_{user_id}")

    suffix = Path(filename or "voice.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        try:
            voice = await asyncio.wait_for(
                asyncio.to_thread(
                    client.clone,
                    name=f"{user_id}_voice",
                    description="User voice for PitchSnap avatar",
                    files=[tmp.name],
                ),
                timeout=_timeout("ELEVENLABS_CLONE_TIMEOUT", 35),
            )
            voice_id = voice.voice_id
        except Exception:
            voice_id = f"mock_voice_{user_id}"

    return _cache_voice(user_id, voice_id)


def _write_mock_audio(text: str, user_id: str, ticker: str) -> str:
    filename = unique_filename(f"{user_id}-{ticker}-mock-pitch", ".wav")
    path = ensure_generated_dir("audio") / filename
    sample_rate = 22050
    duration = max(2.0, min(8.0, len(text) / 24))
    total_frames = int(sample_rate * duration)
    base_freq = 180 + (sum(ord(ch) for ch in ticker) % 90)

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()
        for frame in range(total_frames):
            t = frame / sample_rate
            envelope = min(1.0, frame / (sample_rate * 0.12), (total_frames - frame) / (sample_rate * 0.18))
            voice_wave = math.sin(2 * math.pi * base_freq * t)
            cadence = 0.55 + 0.45 * math.sin(2 * math.pi * 3.2 * t)
            sample = int(10000 * envelope * cadence * voice_wave)
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))

        wav_file.writeframes(bytes(frames))

    return public_url("audio", filename)


def _audio_to_bytes(audio) -> bytes:
    if isinstance(audio, bytes):
        return audio
    if isinstance(audio, bytearray):
        return bytes(audio)
    chunks = []
    for chunk in audio:
        if isinstance(chunk, int):
            chunks.append(bytes([chunk]))
        else:
            chunks.append(chunk)
    return b"".join(chunks)


async def generate_speech(text: str, voice_id: Optional[str], user_id: str, ticker: str) -> Optional[str]:
    if not text.strip():
        return None

    force_mock = _env_truthy("ELEVENLABS_FORCE_MOCK_TTS") or _env_explicit_false("ELEVENLABS_LIVE_TTS")
    if force_mock or not voice_id or voice_id.startswith("mock_voice_"):
        return _write_mock_audio(text, user_id, ticker)

    client = _client()
    if client is None:
        return _write_mock_audio(text, user_id, ticker)

    def generate_audio_bytes() -> bytes:
        audio = client.generate(
            text=text,
            voice=voice_id,
            model=os.getenv("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2"),
        )
        return _audio_to_bytes(audio)

    try:
        chunks = await asyncio.wait_for(
            asyncio.to_thread(generate_audio_bytes),
            timeout=_timeout("ELEVENLABS_TTS_TIMEOUT", 25),
        )
    except Exception:
        return _write_mock_audio(text, user_id, ticker)

    if not chunks:
        return None

    filename = unique_filename(f"{user_id}-{ticker}-pitch", ".mp3")
    path = ensure_generated_dir("audio") / filename
    path.write_bytes(chunks)
    return public_url("audio", filename)
