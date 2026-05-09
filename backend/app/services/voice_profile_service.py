import json
import os
import re
import tempfile
from typing import Any, Optional

from openai import OpenAI


FALLBACK_SLANG = ["honestly", "I like", "I worry"]


def _client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _transcription_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    return str(getattr(response, "text", "") or "").strip()


def _fallback_lingo(transcript: str, prompt: str) -> dict:
    text = transcript or prompt
    words = re.findall(r"\b[a-zA-Z][a-zA-Z'-]{2,}\b", text.lower())
    stop = {
        "about",
        "because",
        "really",
        "think",
        "stock",
        "crypto",
        "market",
        "investment",
        "investing",
        "would",
        "could",
        "should",
        "that",
        "this",
        "with",
        "from",
    }
    candidates = []
    for word in words:
        if word not in stop and word not in candidates:
            candidates.append(word)
    return {
        "transcript": transcript,
        "slang_examples": candidates[:4] or FALLBACK_SLANG,
        "formality": 0.35 if any(w in text.lower() for w in ["lowkey", "ngl", "honestly"]) else 0.5,
        "preferred_phrases": candidates[:6],
        "explanation_depth": "plain_english" if "explain" in text.lower() else "medium",
    }


async def transcribe_voice_sample(audio_bytes: Optional[bytes], filename: str) -> str:
    if not audio_bytes:
        return ""

    client = _client()
    if client is None:
        return ""

    suffix = os.path.splitext(filename or "voice.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        with open(tmp.name, "rb") as audio_file:
            try:
                response = client.audio.transcriptions.create(
                    model=os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1"),
                    file=audio_file,
                    prompt="The speaker is describing investing style, favorite stocks, crypto, risk, and market language.",
                )
            except Exception:
                return ""
    return _transcription_text(response)


async def extract_lingo_profile(transcript: str, prompt: str) -> dict:
    if not transcript:
        return _fallback_lingo("", prompt)

    client = _client()
    if client is None:
        return _fallback_lingo(transcript, prompt)

    system = (
        "Extract a compact investor voice profile from a transcript. "
        "Return JSON only with: slang_examples array, preferred_phrases array, "
        "formality number 0-1, explanation_depth string, and tone_summary string. "
        "Use exact words or short phrases the speaker actually uses where possible."
    )
    user = f"Recording prompt: {prompt}\nTranscript: {transcript}"

    try:
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        content = completion.choices[0].message.content or "{}"
        parsed = json.loads(content)
    except Exception:
        return _fallback_lingo(transcript, prompt)

    fallback = _fallback_lingo(transcript, prompt)
    slang = parsed.get("slang_examples")
    phrases = parsed.get("preferred_phrases")
    return {
        "transcript": transcript,
        "slang_examples": slang if isinstance(slang, list) and slang else fallback["slang_examples"],
        "preferred_phrases": phrases if isinstance(phrases, list) and phrases else fallback["preferred_phrases"],
        "formality": max(0.0, min(1.0, float(parsed.get("formality", fallback["formality"])))),
        "explanation_depth": str(parsed.get("explanation_depth", fallback["explanation_depth"])),
        "tone_summary": str(parsed.get("tone_summary", "")),
    }
