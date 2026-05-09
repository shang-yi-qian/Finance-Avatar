import json
import os
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


async def clone_voice_once(user_id: str, audio_bytes: Optional[bytes], filename: str) -> str:
    cache = _load_voice_cache()
    cached_voice_id = cache.get(user_id)
    if cached_voice_id and not cached_voice_id.startswith("mock_voice_"):
        return cached_voice_id
    if cached_voice_id and cached_voice_id.startswith("mock_voice_") and not audio_bytes:
        return cache[user_id]

    if not audio_bytes:
        return f"mock_voice_{user_id}"

    client = _client()
    if client is None:
        return f"mock_voice_{user_id}"

    suffix = Path(filename or "voice.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        try:
            voice = client.clone(
                name=f"{user_id}_voice",
                description="User voice for PitchSnap avatar",
                files=[tmp.name],
            )
            voice_id = voice.voice_id
        except Exception:
            voice_id = f"mock_voice_{user_id}"

    cache[user_id] = voice_id
    _save_voice_cache(cache)
    return voice_id


async def generate_speech(text: str, voice_id: Optional[str], user_id: str, ticker: str) -> Optional[str]:
    if not voice_id or voice_id.startswith("mock_voice_"):
        return None

    client = _client()
    if client is None:
        return None

    try:
        audio = client.generate(
            text=text,
            voice=voice_id,
            model=os.getenv("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2"),
        )
        chunks = b"".join(chunk for chunk in audio)
    except Exception:
        return None

    if not chunks:
        return None

    filename = unique_filename(f"{user_id}-{ticker}-pitch", ".mp3")
    path = ensure_generated_dir("audio") / filename
    path.write_bytes(chunks)
    return public_url("audio", filename)
