"""In-memory style-profile store + recent-pitch cache.

This is the source of truth for the Phase 3 personalization loop. Each user's
style profile lives here keyed by ``user_id`` and is mutated by the feedback
route. The frontend always sends its latest snapshot with ``/pitch`` so the
store also accepts incoming snapshots and merges them with any server-side
adjustments (e.g. flagged terms added from a previous "too jargon-y" signal).

We intentionally avoid a database here. Demo flow runs in a single backend
process, and Convex stores any persistent slice on the frontend side.
"""

from __future__ import annotations

import time
from copy import deepcopy
from typing import Any

DEFAULT_PROFILE: dict[str, Any] = {
    "user_id": "live_demo_user",
    "tone": {
        "formality": 0.25,
        "emoji_usage": 0.35,
        "slang_examples": ["lowkey", "bag", "ngl", "fam"],
    },
    "jargon_tolerance": {
        "level": 0.55,
        "known_terms": ["P/E", "EPS", "beta", "market cap"],
        "unknown_or_flagged": [],
    },
    "risk_language": {"tolerance": 0.72, "preferred_framing": "upside_first"},
    "explanation_depth": "medium",
    "thematic_interests": ["semiconductors", "AI infrastructure", "cloud", "consumer tech"],
    "horizon": "6_months_to_2_years",
    "feedback_history": [],
}

_PITCH_TTL_SECONDS = 60 * 60  # 1 hour is plenty for the demo

_profiles: dict[str, dict[str, Any]] = {}
_pitch_cache: dict[str, dict[str, Any]] = {}


def _seed_default(user_id: str) -> dict[str, Any]:
    seeded = deepcopy(DEFAULT_PROFILE)
    seeded["user_id"] = user_id
    return seeded


def get_profile(user_id: str) -> dict[str, Any]:
    """Return a deep copy of the profile for ``user_id`` (creating one if missing)."""
    if user_id not in _profiles:
        _profiles[user_id] = _seed_default(user_id)
    return deepcopy(_profiles[user_id])


def upsert_profile(user_id: str, snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Merge a frontend snapshot into the stored profile.

    We preserve any server-only state (e.g. ``unknown_or_flagged`` and the
    feedback history) when the frontend sends an outdated copy.
    """

    existing = _profiles.get(user_id) or _seed_default(user_id)

    if not snapshot:
        _profiles[user_id] = existing
        return deepcopy(existing)

    merged = deepcopy(existing)

    for key, value in snapshot.items():
        if key in {"jargon_tolerance", "tone", "risk_language"} and isinstance(value, dict):
            base = merged.get(key, {}) or {}
            base.update({k: v for k, v in value.items() if v is not None})
            merged[key] = base
        elif key == "feedback_history":
            continue  # always keep server-side history
        elif value is not None:
            merged[key] = value

    # Make sure server-side flagged terms are not erased by an empty snapshot.
    server_flagged = (existing.get("jargon_tolerance") or {}).get("unknown_or_flagged") or []
    snapshot_flagged = (snapshot.get("jargon_tolerance") or {}).get("unknown_or_flagged") or []
    merged_jt = merged.setdefault("jargon_tolerance", {})
    merged_jt["unknown_or_flagged"] = sorted(
        {*server_flagged, *snapshot_flagged}
    )

    merged["user_id"] = user_id
    _profiles[user_id] = merged
    return deepcopy(merged)


def replace_profile(user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Overwrite the stored profile entirely. Used by feedback updates."""
    profile = deepcopy(profile)
    profile["user_id"] = user_id
    _profiles[user_id] = profile
    return deepcopy(profile)


def remember_pitch(pitch_id: str, *, user_id: str, ticker: str, spoken_text: str) -> None:
    if not pitch_id:
        return
    _pitch_cache[pitch_id] = {
        "user_id": user_id,
        "ticker": ticker,
        "spoken_text": spoken_text,
        "ts": time.time(),
    }
    _evict_stale_pitches()


def get_pitch(pitch_id: str) -> dict[str, Any] | None:
    record = _pitch_cache.get(pitch_id)
    if not record:
        return None
    if time.time() - record.get("ts", 0) > _PITCH_TTL_SECONDS:
        _pitch_cache.pop(pitch_id, None)
        return None
    return record


def _evict_stale_pitches() -> None:
    now = time.time()
    stale = [pid for pid, record in _pitch_cache.items() if now - record.get("ts", 0) > _PITCH_TTL_SECONDS]
    for pid in stale:
        _pitch_cache.pop(pid, None)
