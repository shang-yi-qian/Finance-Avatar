import base64
import os
import tempfile
from typing import Any, Optional

from openai import OpenAI

from app.services.storage_service import ensure_generated_dir, public_url, unique_filename


def _client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _avatar_prompt(answers: dict, lingo: dict) -> str:
    interests = ", ".join(answers.get("thematic_interests", [])[:5]) or "investing"
    asset_types = ", ".join(
        sorted({str(item.get("assetType") or item.get("asset_type") or "stock") for item in answers.get("portfolio", []) if isinstance(item, dict)})
    )
    phrases = ", ".join(lingo.get("preferred_phrases", [])[:4])
    return (
        "Create a stylized animated avatar portrait for a personalized investment assistant. "
        "Use the uploaded selfie only as a loose identity reference; do not make it photorealistic. "
        "Style: polished Pixar-ish cartoon, head-and-shoulders composition, expressive but professional. "
        "Props: over-ear headphones, a glowing GPU chip floating beside the shoulder, subtle circuit-board patterns on clothing, "
        "and a compact financial dashboard reflection. "
        f"Investor themes: {interests}. Asset types: {asset_types or 'stocks and crypto'}. "
        f"Tone cues from their speech: {phrases or 'clear, conversational, confident'}. "
        "Background: dark modern finance UI backdrop, tasteful blue/cyan lighting. "
        "Square 1024x1024. Not photorealistic. No text, no logos, no watermark."
    )


def _save_b64_image(user_id: str, b64_json: str, index: int) -> str:
    image_bytes = base64.b64decode(b64_json)
    filename = unique_filename(f"{user_id}-avatar-{index}", ".png")
    path = ensure_generated_dir("avatars") / filename
    path.write_bytes(image_bytes)
    return public_url("avatars", filename)


def _extract_b64_items(response: Any) -> list[str]:
    data = getattr(response, "data", None) or []
    items = []
    for item in data:
        b64_json = getattr(item, "b64_json", None)
        if b64_json:
            items.append(b64_json)
    return items


def fallback_avatar_variants(user_id: str) -> list[str]:
    encoded_user = user_id.replace("_", "+")
    return [
        f"https://placehold.co/1024x1024/111827/60a5fa?text={encoded_user}+Avatar+1",
        f"https://placehold.co/1024x1024/0f172a/22d3ee?text={encoded_user}+Avatar+2",
        f"https://placehold.co/1024x1024/172554/f8fafc?text={encoded_user}+Avatar+3",
    ]


async def generate_avatar_variants(
    user_id: str,
    selfie_bytes: Optional[bytes],
    selfie_filename: str,
    answers: dict,
    lingo: dict,
) -> list[str]:
    client = _client()
    if client is None:
        return fallback_avatar_variants(user_id)

    prompt = _avatar_prompt(answers, lingo)
    b64_items: list[str] = []

    if selfie_bytes:
        suffix = os.path.splitext(selfie_filename or "selfie.png")[1] or ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(selfie_bytes)
            tmp.flush()
            with open(tmp.name, "rb") as image_file:
                try:
                    response = client.images.edit(
                        model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
                        image=image_file,
                        prompt=prompt,
                        n=3,
                        size="1024x1024",
                        response_format="b64_json",
                    )
                    b64_items = _extract_b64_items(response)
                except Exception:
                    b64_items = []

    if not b64_items:
        try:
            response = client.images.generate(
                model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
                prompt=prompt,
                n=3,
                size="1024x1024",
                response_format="b64_json",
            )
            b64_items = _extract_b64_items(response)
        except Exception:
            return fallback_avatar_variants(user_id)

    if not b64_items:
        return fallback_avatar_variants(user_id)

    return [_save_b64_image(user_id, b64_json, index + 1) for index, b64_json in enumerate(b64_items[:3])]
