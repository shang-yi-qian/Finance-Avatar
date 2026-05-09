from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional
import json

router = APIRouter()


@router.post("/onboard")
async def onboard(
    selfie: Optional[UploadFile] = File(None),
    voice_recording: Optional[UploadFile] = File(None),
    quiz_answers: str = Form("{}"),
):
    # Phase 4: call gpt_image_service + elevenlabs_service + save to Convex
    answers = json.loads(quiz_answers)
    return {
        "status": "ok",
        "user_id": answers.get("user_id", "kai_demo"),
        "avatar_variants": [
            "https://placehold.co/1024x1024/1a1a2e/ffffff?text=Avatar+1",
            "https://placehold.co/1024x1024/16213e/ffffff?text=Avatar+2",
            "https://placehold.co/1024x1024/0f3460/ffffff?text=Avatar+3",
        ],
        "voice_id": "mock_voice_id",
    }
