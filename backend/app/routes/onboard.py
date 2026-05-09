from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional
import json

from app.services.elevenlabs_service import clone_voice_once
from app.services.gpt_image_service import generate_avatar_variants
from app.services.voice_profile_service import extract_lingo_profile, transcribe_voice_sample

router = APIRouter()


@router.post("/onboard")
async def onboard(
    selfie: Optional[UploadFile] = File(None),
    voice_recording: Optional[UploadFile] = File(None),
    quiz_answers: str = Form("{}"),
):
    answers = json.loads(quiz_answers)
    user_id = answers.get("user_id", "live_demo_user")
    voice_prompt = answers.get("voice_prompt", "")

    selfie_bytes = await selfie.read() if selfie else None
    voice_bytes = await voice_recording.read() if voice_recording else None

    transcript = await transcribe_voice_sample(
        voice_bytes,
        voice_recording.filename if voice_recording else "voice.webm",
    )
    lingo_profile = await extract_lingo_profile(transcript, voice_prompt)
    avatar_variants = await generate_avatar_variants(
        user_id=user_id,
        selfie_bytes=selfie_bytes,
        selfie_filename=selfie.filename if selfie else "selfie.png",
        answers=answers,
        lingo=lingo_profile,
    )
    voice_id = await clone_voice_once(
        user_id,
        voice_bytes,
        voice_recording.filename if voice_recording else "voice.webm",
    )

    return {
        "status": "ok",
        "user_id": user_id,
        "avatar_variants": avatar_variants,
        "voice_id": voice_id,
        "voice_transcript": transcript,
        "style_profile_patch": lingo_profile,
    }
