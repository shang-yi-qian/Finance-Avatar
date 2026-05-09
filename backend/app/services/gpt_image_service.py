import asyncio
import base64
from html import escape
import os
import tempfile
from typing import Any, Callable, Optional, Tuple

import httpx
from openai import OpenAI

from app.services.storage_service import ensure_generated_dir, public_url, unique_filename


ReferenceImage = Tuple[bytes, str]


def _api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY")


def _client() -> Optional[OpenAI]:
    api_key = _api_key()
    if not api_key:
        return None
    return OpenAI(api_key=api_key, timeout=float(os.getenv("OPENAI_TIMEOUT", "30")))


def _timeout(name: str, fallback: float) -> float:
    try:
        return float(os.getenv(name, str(fallback)))
    except ValueError:
        return fallback


def _avatar_prompt(answers: dict, lingo: dict) -> str:
    interests = ", ".join(answers.get("thematic_interests", [])[:5]) or "investing"
    asset_types = ", ".join(
        sorted({str(item.get("assetType") or item.get("asset_type") or "stock") for item in answers.get("portfolio", []) if isinstance(item, dict)})
    )
    phrases = ", ".join(lingo.get("preferred_phrases", [])[:4])
    return (
        "Transform the reference media into a brand-new, highly recognizable stylized 3D avatar portrait for a personalized "
        "investment assistant. Use the selfie as the main identity reference and any extra face-motion frames as expression "
        "references only. Preserve the person's face shape, hairstyle, hair color, skin tone, age range, eyewear, facial hair, "
        "and natural facial proportions. "
        "The output must be a coherent rendered 3D character, not the original camera photo. Do not place the selfie inside a "
        "card, phone frame, camera crop, UI panel, or border. Do not draw props as flat icons over the photo. Do not create a "
        "generic icon, stick figure, logo, mascot, or unrelated character. "
        "Style: polished semi-real 3D cartoon portrait, head-and-shoulders composition, expressive but professional, natural "
        "speaking-ready face with subtle smile and clear eyes. Props may be integrated into the scene as real 3D objects: "
        "over-ear headphones, a glowing GPU chip floating beside the shoulder, subtle circuit-board patterns on clothing, "
        "and a compact financial dashboard reflection. "
        f"Investor themes: {interests}. Asset types: {asset_types or 'stocks and crypto'}. "
        f"Tone cues from their speech: {phrases or 'clear, conversational, confident'}. "
        "Background: dark modern finance UI backdrop, tasteful blue/cyan lighting. "
        "Square 1024x1024. Semi-real 3D avatar, not photorealistic. No text, no captions, no logos, no watermark."
    )


def _variant_prompt(base_prompt: str, index: int) -> str:
    variants = [
        "Variant 1: friendly analyst twin, calm confident expression, balanced studio lighting.",
        "Variant 2: more cinematic, stronger 3D depth, slight turn of the head, premium tech lighting.",
        "Variant 3: warmer and more expressive, natural talking pose, polished creator-avatar finish.",
    ]
    return f"{base_prompt}\n{variants[(index - 1) % len(variants)]}"


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


def _looks_like_b64_image(value: str) -> bool:
    if len(value) < 1000:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r")
    return all(char in allowed for char in value[:512])


def _extract_b64_from_payload(payload: Any) -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"result", "b64_json"} and isinstance(value, str) and _looks_like_b64_image(value):
                found.append(value)
            else:
                found.extend(_extract_b64_from_payload(value))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(_extract_b64_from_payload(item))
    return found


def _write_fallback_avatar(user_id: str, index: int, answers: Optional[dict], lingo: Optional[dict]) -> str:
    palettes = [
        ("#0f172a", "#22d3ee", "#60a5fa"),
        ("#111827", "#a78bfa", "#34d399"),
        ("#172554", "#f59e0b", "#38bdf8"),
    ]
    bg, accent, accent_2 = palettes[(index - 1) % len(palettes)]
    display_name = escape(str((answers or {}).get("display_name") or user_id).replace("_", " ").title()[:22])
    raw_themes = (answers or {}).get("thematic_interests") or []
    if not isinstance(raw_themes, list):
        raw_themes = [str(raw_themes)]
    raw_phrases = (lingo or {}).get("preferred_phrases") or []
    if not isinstance(raw_phrases, list):
        raw_phrases = [str(raw_phrases)]
    themes = ", ".join(str(item) for item in raw_themes[:2]) or "AI markets"
    phrase = ", ".join(str(item) for item in raw_phrases[:2]) or themes
    subtitle = escape(str(phrase)[:36])

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <defs>
    <radialGradient id="glow" cx="50%" cy="35%" r="65%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.42"/>
      <stop offset="55%" stop-color="{bg}" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#05070d"/>
    </radialGradient>
    <linearGradient id="shirt" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.82"/>
      <stop offset="100%" stop-color="{accent_2}" stop-opacity="0.84"/>
    </linearGradient>
  </defs>
  <rect width="1024" height="1024" fill="url(#glow)"/>
  <g opacity="0.28" stroke="{accent_2}" stroke-width="3" fill="none">
    <path d="M144 220h210v78h126v96h194"/>
    <path d="M180 750h190v-92h180v-76h288"/>
    <path d="M720 210v128h112v194"/>
    <circle cx="354" cy="298" r="10" fill="{accent_2}"/>
    <circle cx="550" cy="582" r="10" fill="{accent_2}"/>
    <circle cx="832" cy="532" r="10" fill="{accent_2}"/>
  </g>
  <g transform="translate(512 520)">
    <ellipse cx="0" cy="272" rx="260" ry="92" fill="#030712" opacity="0.36"/>
    <path d="M-248 350c30-178 132-270 248-270s218 92 248 270z" fill="url(#shirt)"/>
    <path d="M-180 282c88 52 272 54 360 0" stroke="#0f172a" stroke-width="22" opacity="0.42" fill="none"/>
    <circle cx="0" cy="-88" r="188" fill="#f8d3b1"/>
    <path d="M-170-126c42-142 268-156 342-26 28 49 16 91 5 120-34-76-108-120-204-120-60 0-108 14-143 26z" fill="#1f2937"/>
    <circle cx="-74" cy="-78" r="16" fill="#111827"/>
    <circle cx="74" cy="-78" r="16" fill="#111827"/>
    <path d="M-66 12c42 34 96 34 132 0" stroke="#111827" stroke-width="14" stroke-linecap="round" fill="none"/>
    <path d="M-202-94c-58 34-72 130-24 190" stroke="{accent_2}" stroke-width="34" stroke-linecap="round" fill="none"/>
    <path d="M202-94c58 34 72 130 24 190" stroke="{accent_2}" stroke-width="34" stroke-linecap="round" fill="none"/>
    <rect x="-274" y="-144" width="54" height="150" rx="28" fill="#111827"/>
    <rect x="220" y="-144" width="54" height="150" rx="28" fill="#111827"/>
  </g>
  <g transform="translate(742 316)">
    <rect x="-84" y="-84" width="168" height="168" rx="28" fill="#020617" stroke="{accent}" stroke-width="10"/>
    <rect x="-46" y="-46" width="92" height="92" rx="14" fill="{accent}" opacity="0.9"/>
    <g stroke="{accent_2}" stroke-width="8" stroke-linecap="round">
      <path d="M-118-44h34M-118 0h34M-118 44h34M84-44h34M84 0h34M84 44h34"/>
      <path d="M-44-118v34M0-118v34M44-118v34M-44 84v34M0 84v34M44 84v34"/>
    </g>
  </g>
  <text x="512" y="895" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="44" font-weight="700" fill="#f8fafc">{display_name}</text>
  <text x="512" y="946" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="27" fill="#cbd5e1">{subtitle}</text>
</svg>"""
    filename = unique_filename(f"{user_id}-fallback-avatar-{index}", ".svg")
    path = ensure_generated_dir("avatars") / filename
    path.write_text(svg, encoding="utf-8")
    return public_url("avatars", filename)


def _image_mime(filename: str) -> str:
    suffix = os.path.splitext(filename or "")[1].lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _input_image_content(image_bytes: bytes, filename: str) -> dict:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return {
        "type": "input_image",
        "image_url": f"data:{_image_mime(filename)};base64,{encoded}",
    }


async def _generate_with_responses_api(
    prompt: str,
    references: list[ReferenceImage],
    progress_callback: Optional[Callable[[str], None]] = None,
) -> list[str]:
    api_key = _api_key()
    if not api_key or not references:
        return []

    timeout = _timeout("OPENAI_IMAGE_RESPONSES_TIMEOUT", 90)
    model = os.getenv("OPENAI_IMAGE_REASONING_MODEL", "gpt-5.5")
    endpoint = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/") + "/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as http:
        async def render_variant(index: int) -> Optional[str]:
            if progress_callback:
                progress_callback(f"GPT Image 2 is rendering avatar variant {index}/3 with high-fidelity reference inputs.")
            content = [{"type": "input_text", "text": _variant_prompt(prompt, index)}]
            content.extend(_input_image_content(image_bytes, filename) for image_bytes, filename in references[:4])
            payload = {
                "model": model,
                "input": [{"role": "user", "content": content}],
                "tools": [
                    {
                        "type": "image_generation",
                        "size": "1024x1024",
                        "input_fidelity": "high",
                    }
                ],
            }
            response = await http.post(endpoint, headers=headers, json=payload)
            if response.status_code >= 400:
                if progress_callback:
                    progress_callback(f"Avatar variant {index}/3 did not return from the Responses path; fallback will try if needed.")
                return None
            image_items = _extract_b64_from_payload(response.json())
            if image_items:
                if progress_callback:
                    progress_callback(f"Avatar variant {index}/3 generated.")
                return image_items[0]
            return None

        rendered = await asyncio.gather(*(render_variant(index) for index in range(1, 4)), return_exceptions=True)

    return [item for item in rendered if isinstance(item, str)][:3]


async def _generate_with_image_edit(
    client: OpenAI,
    prompt: str,
    selfie_bytes: bytes,
    selfie_filename: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> list[str]:
    suffix = os.path.splitext(selfie_filename or "selfie.png")[1] or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(selfie_bytes)
        tmp.flush()
        tmp_path = tmp.name

    def edit_image() -> Any:
        with open(tmp_path, "rb") as image_file:
            return client.images.edit(
                model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2"),
                image=image_file,
                prompt=prompt,
                n=3,
                size="1024x1024",
                response_format="b64_json",
                extra_body={"input_fidelity": "high"},
            )

    try:
        if progress_callback:
            progress_callback("Using OpenAI image-edit fallback with high input fidelity for any missing variants.")
        response = await asyncio.wait_for(
            asyncio.to_thread(edit_image),
            timeout=_timeout("OPENAI_IMAGE_EDIT_TIMEOUT", 60),
        )
        return _extract_b64_items(response)
    finally:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass


def fallback_avatar_variants(
    user_id: str,
    answers: Optional[dict] = None,
    lingo: Optional[dict] = None,
) -> list[str]:
    return [_write_fallback_avatar(user_id, index, answers, lingo) for index in range(1, 4)]


async def generate_avatar_variants(
    user_id: str,
    selfie_bytes: Optional[bytes],
    selfie_filename: str,
    answers: dict,
    lingo: dict,
    reference_images: Optional[list[ReferenceImage]] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> list[str]:
    client = _client()
    if client is None:
        return fallback_avatar_variants(user_id, answers, lingo)

    prompt = _avatar_prompt(answers, lingo)
    b64_items: list[str] = []
    references: list[ReferenceImage] = []
    if selfie_bytes:
        references.append((selfie_bytes, selfie_filename or "selfie.png"))
    references.extend(reference_images or [])

    if references:
        try:
            b64_items = await _generate_with_responses_api(prompt, references, progress_callback)
        except Exception:
            b64_items = []

        if len(b64_items) < 3 and selfie_bytes:
            try:
                edit_items = await _generate_with_image_edit(
                    client,
                    prompt,
                    selfie_bytes,
                    selfie_filename,
                    progress_callback,
                )
                b64_items.extend(edit_items[: 3 - len(b64_items)])
            except Exception:
                pass

        if not b64_items and selfie_bytes:
            raise RuntimeError("OpenAI avatar generation failed before producing a selfie-derived 3D avatar.")

    if not b64_items:
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.images.generate,
                    model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2"),
                    prompt=prompt,
                    n=3,
                    size="1024x1024",
                    response_format="b64_json",
                ),
                timeout=_timeout("OPENAI_IMAGE_GENERATE_TIMEOUT", 60),
            )
            b64_items = _extract_b64_items(response)
        except Exception:
            return fallback_avatar_variants(user_id, answers, lingo)

    if not b64_items:
        return fallback_avatar_variants(user_id, answers, lingo)

    return [_save_b64_image(user_id, b64_json, index + 1) for index, b64_json in enumerate(b64_items[:3])]
