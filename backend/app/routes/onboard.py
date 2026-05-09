import asyncio
import time
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import List, Optional
import json

from app.services.elevenlabs_service import clone_voice_once
from app.services.gpt_image_service import generate_avatar_variants
from app.services.voice_profile_service import extract_lingo_profile, transcribe_voice_sample

router = APIRouter()

ONBOARD_PROGRESS: dict[str, dict] = {}


def _publish_progress(job_id: str, stage: str, message: str, status: str = "running") -> None:
    state = ONBOARD_PROGRESS.setdefault(job_id, {"events": [], "done": False})
    state["events"].append(
        {
            "stage": stage,
            "message": message,
            "status": status,
            "timestamp": time.time(),
        }
    )
    if status in {"complete", "error"}:
        state["done"] = True


@router.get("/onboard/progress/{job_id}")
async def onboard_progress(job_id: str):
    async def event_stream():
        cursor = 0
        started_at = time.time()
        sent_waiting = False

        while True:
            state = ONBOARD_PROGRESS.get(job_id)
            if state is None:
                if not sent_waiting:
                    yield f"data: {json.dumps({'stage': 'waiting', 'message': 'Waiting for upload to reach backend.', 'status': 'pending', 'timestamp': time.time()})}\n\n"
                    sent_waiting = True
                if time.time() - started_at > 420:
                    break
                await asyncio.sleep(0.35)
                continue

            events = state.get("events", [])
            while cursor < len(events):
                yield f"data: {json.dumps(events[cursor])}\n\n"
                cursor += 1

            if state.get("done"):
                await asyncio.sleep(1.5)
                ONBOARD_PROGRESS.pop(job_id, None)
                break

            await asyncio.sleep(0.35)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/onboard")
async def onboard(
    selfie: Optional[UploadFile] = File(None),
    voice_recording: Optional[UploadFile] = File(None),
    face_reference_frames: Optional[List[UploadFile]] = File(None),
    quiz_answers: str = Form("{}"),
    job_id: Optional[str] = Form(None),
):
    answers = json.loads(quiz_answers)
    job_id = job_id or answers.get("job_id") or uuid4().hex
    user_id = answers.get("user_id", "live_demo_user")
    voice_prompt = answers.get("voice_prompt", "")
    existing_voice_id = answers.get("voice_id")

    try:
        _publish_progress(job_id, "upload", "Upload received. Reading camera image and voice sample.")
        selfie_bytes = await selfie.read() if selfie else None
        voice_bytes = await voice_recording.read() if voice_recording else None
        reference_images = []
        for frame in face_reference_frames or []:
            frame_bytes = await frame.read()
            if frame_bytes:
                reference_images.append((frame_bytes, frame.filename or "face-reference.jpg"))

        _publish_progress(job_id, "transcribe", "OpenAI transcription is reading the recorded answer.")
        transcript = await transcribe_voice_sample(
            voice_bytes,
            voice_recording.filename if voice_recording else "voice.webm",
        )
        if transcript:
            _publish_progress(job_id, "transcribe", "Voice transcript captured. Extracting lingo and tone.")
        else:
            _publish_progress(job_id, "transcribe", "Transcript unavailable or timed out. Falling back to prompt-based lingo.")

        _publish_progress(job_id, "lingo", "LLM is extracting slang, preferred phrases, and explanation depth.")
        lingo_profile = await extract_lingo_profile(transcript, voice_prompt)

        _publish_progress(
            job_id,
            "image",
            "GPT Image 2 is transforming the selfie and motion frames into 3D avatar variants.",
        )
        avatar_variants = await generate_avatar_variants(
            user_id=user_id,
            selfie_bytes=selfie_bytes,
            selfie_filename=selfie.filename if selfie else "selfie.png",
            answers=answers,
            lingo=lingo_profile,
            reference_images=reference_images,
            progress_callback=lambda message: _publish_progress(job_id, "image", message),
        )

        _publish_progress(job_id, "voice", "ElevenLabs is registering or reusing the cloned voice profile.")
        voice_id = await clone_voice_once(
            user_id,
            voice_bytes,
            voice_recording.filename if voice_recording else "voice.webm",
            existing_voice_id=existing_voice_id,
        )

        _publish_progress(job_id, "complete", "Avatar variants and voice profile are ready.", "complete")
        return {
            "status": "ok",
            "user_id": user_id,
            "avatar_variants": avatar_variants,
            "voice_id": voice_id,
            "voice_transcript": transcript,
            "style_profile_patch": lingo_profile,
        }
    except Exception:
        _publish_progress(job_id, "error", "Onboarding failed before completion. Check backend logs for the API error.", "error")
        raise
