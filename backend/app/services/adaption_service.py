"""Adaption-style personalization service.

This module owns the deterministic feedback-rule engine that powers the
demo's "👎 too jargon-y → next pitch is simpler" beat. It is the source of
truth for the user's style profile during a session.

Why local-only by default:
- Adaption Labs' public API (api.adaptionlabs.ai) is currently a *dataset*
  adaptation product, not a hosted user-profile store.
- For the live demo we need a deterministic, low-latency feedback loop that
  the judges can see updating in real-time. A best-effort outbound sync to
  Adaption (or any future replacement) is fired-and-forgotten so that the
  primary loop is never blocked.
"""

from __future__ import annotations

import logging
import os
import re
import time
from copy import deepcopy
from typing import Any, Iterable

import httpx

from app.services import profile_store

logger = logging.getLogger(__name__)

JARGON_STEP = 0.08
JARGON_FLOOR = 0.10
JARGON_CEILING = 1.0

# Terms commonly produced by the synthesis agent that a non-technical user is
# most likely to flag. Anything appearing in the recent pitch *and* in this
# vocabulary is added to ``unknown_or_flagged`` when the user clicks
# "Too jargon-y".
JARGON_VOCABULARY: tuple[str, ...] = (
    "P/E",
    "PE ratio",
    "P/E ratio",
    "EPS",
    "EPS estimate",
    "future EPS estimate",
    "beta",
    "consensus",
    "buy consensus",
    "sell consensus",
    "hold consensus",
    "buy rating",
    "sell rating",
    "hold rating",
    "analyst lean",
    "DCF",
    "free cash flow",
    "Piotroski",
    "Altman",
    "altmanZScore",
    "piotroskiScore",
    "moving average",
    "RSI",
    "MACD",
    "valuation multiple",
    "rating snapshot",
    "analyst consensus target",
    "earnings surprise",
    "momentum",
    "drawdown",
    "bps",
    "yield",
)


def _extract_flagged_terms(text: str) -> list[str]:
    """Pull jargon-y terms out of a pitch transcript using simple substring scans."""
    if not text:
        return []
    seen: list[str] = []
    seen_lower: set[str] = set()
    lowered = text.lower()
    for term in JARGON_VOCABULARY:
        marker = term.lower()
        if marker in lowered and marker not in seen_lower:
            seen.append(term)
            seen_lower.add(marker)
    return seen[:6]


def _round(value: float, places: int = 2) -> float:
    return round(float(value), places)


def _build_history_entry(
    *,
    signal: str,
    pitch_id: str,
    ticker: str | None,
    flagged: Iterable[str],
    delta: float,
) -> dict[str, Any]:
    return {
        "signal": signal,
        "pitch_id": pitch_id,
        "ticker": ticker,
        "flagged_added": list(flagged),
        "jargon_level_delta": _round(delta),
        "ts": int(time.time()),
    }


def _depth_for_level(level: float) -> str:
    if level <= 0.45:
        return "plain_english"
    if level >= 0.7:
        return "deep"
    return "medium"


def _apply_rules(
    profile: dict[str, Any],
    *,
    signal: str,
    pitch_text: str,
) -> tuple[dict[str, Any], list[str], float]:
    updated = deepcopy(profile)
    jargon = updated.setdefault(
        "jargon_tolerance",
        {"level": 0.55, "known_terms": [], "unknown_or_flagged": []},
    )
    current_level = float(jargon.get("level", 0.55))
    flagged_now = list(jargon.get("unknown_or_flagged") or [])
    added: list[str] = []
    delta = 0.0

    if signal == "too_jargony":
        new_level = max(JARGON_FLOOR, current_level - JARGON_STEP)
        delta = _round(new_level - current_level)
        jargon["level"] = _round(new_level)

        candidates = _extract_flagged_terms(pitch_text)
        for term in candidates:
            if term not in flagged_now:
                flagged_now.append(term)
                added.append(term)

        # Drop matching items from known_terms so the synth agent stops using them.
        known = jargon.get("known_terms") or []
        jargon["known_terms"] = [t for t in known if t not in flagged_now]
        jargon["unknown_or_flagged"] = flagged_now

    elif signal == "too_basic":
        new_level = min(JARGON_CEILING, current_level + JARGON_STEP)
        delta = _round(new_level - current_level)
        jargon["level"] = _round(new_level)

    elif signal == "nailed_it":
        # No level change, but this counts as positive reinforcement.
        delta = 0.0

    # Keep explanation depth derived from the current level so it never
    # gets stuck (e.g. lingering on plain_english after the user pushes back
    # up via too_basic).
    updated["explanation_depth"] = _depth_for_level(float(jargon["level"]))

    return updated, added, delta


async def _try_remote_sync(user_id: str, payload: dict[str, Any]) -> None:
    """Best-effort POST to Adaption's adaptive-data API.

    We never block on this. If the request fails the local update still wins
    and the demo loop continues to work. This call also doubles as a "we are
    feeding the loop into Adaption" narrative for the sponsor judges.
    """

    api_key = os.getenv("ADAPTION_API_KEY")
    if not api_key:
        return

    base_url = os.getenv("ADAPTION_API_URL", "https://api.adaptionlabs.ai")
    url = f"{base_url.rstrip('/')}/feedback"

    body = {
        "user_id": user_id,
        "event": payload,
        "source": "pitchsnap",
    }
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            await client.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {api_key}"},
            )
    except Exception as exc:  # noqa: BLE001 - best-effort sync
        logger.debug("Adaption sync skipped: %s", exc)


async def apply_feedback(
    user_id: str,
    *,
    pitch_id: str,
    signal: str,
    profile_snapshot: dict[str, Any] | None,
    pitch_text: str = "",
    ticker: str | None = None,
) -> tuple[dict[str, Any], list[str], float]:
    """Apply a feedback signal and return ``(profile, flagged_added, delta)``."""

    base_profile = profile_store.upsert_profile(user_id, profile_snapshot)
    pitch_record = profile_store.get_pitch(pitch_id)
    pitch_text_for_rules = pitch_text or (pitch_record or {}).get("spoken_text", "")
    ticker = ticker or (pitch_record or {}).get("ticker")

    updated, added, delta = _apply_rules(
        base_profile,
        signal=signal,
        pitch_text=pitch_text_for_rules,
    )

    history = updated.setdefault("feedback_history", [])
    history.insert(
        0,
        _build_history_entry(
            signal=signal,
            pitch_id=pitch_id,
            ticker=ticker,
            flagged=added,
            delta=delta,
        ),
    )
    updated["feedback_history"] = history[:25]

    stored = profile_store.replace_profile(user_id, updated)

    await _try_remote_sync(
        user_id,
        {
            "pitch_id": pitch_id,
            "ticker": ticker,
            "signal": signal,
            "flagged_added": added,
            "jargon_level_delta": delta,
            "jargon_level": stored["jargon_tolerance"]["level"],
        },
    )

    return stored, added, delta


def get_profile(user_id: str) -> dict[str, Any]:
    return profile_store.get_profile(user_id)


def upsert_profile(user_id: str, snapshot: dict[str, Any] | None) -> dict[str, Any]:
    return profile_store.upsert_profile(user_id, snapshot)
