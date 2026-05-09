"""Exa-backed research subagent service.

The research agent (``app.agents.research.run_research``) imports
``search`` from this module. We use Exa's neural search to pull the most
relevant 7-day news + earnings commentary for a ticker, then classify the
corpus into ``{news_summary, earnings_sentiment, analyst_tone,
conviction_signal}`` using an OpenAI mini model. If OpenAI is unavailable we
fall back to a deterministic keyword heuristic so the pitch loop never
breaks during the demo.

Sponsor track narrative ("Most Creative Use of Exa"):
- Two parallel neural queries per ticker (news + earnings).
- Time-bound (`start_published_date = today - days`) so we only see fresh signal.
- Highlights, not full articles, are sent to the classifier — keeps token
  cost low and the summary tight.
- 5-minute per-ticker cache so we never re-pay Exa during a stage demo.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import httpx

logger = logging.getLogger(__name__)

EXA_BASE_URL = "https://api.exa.ai"
DEFAULT_RESULTS_PER_QUERY = 5
CACHE_TTL_SECONDS = 5 * 60
LLM_MODEL = os.getenv("EXA_CLASSIFIER_MODEL", "gpt-4o-mini")

_BULLISH_TERMS = (
    "beat",
    "beats",
    "outperform",
    "raised guidance",
    "upgrade",
    "record",
    "surge",
    "rally",
    "strong demand",
    "profit",
    "growth",
    "tailwind",
    "buy rating",
)
_BEARISH_TERMS = (
    "miss",
    "missed",
    "underperform",
    "lowered guidance",
    "downgrade",
    "cut",
    "decline",
    "drop",
    "weak demand",
    "loss",
    "headwind",
    "investigation",
    "lawsuit",
    "sell rating",
)

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


@dataclass
class _ExaResult:
    title: str
    url: str
    published_date: str | None
    text: str
    highlights: list[str]


class ExaServiceError(RuntimeError):
    """Raised when Exa cannot return any usable signal."""


# ---------------------------------------------------------------------------
# Exa HTTP client
# ---------------------------------------------------------------------------


async def _exa_search(
    *,
    api_key: str,
    query: str,
    start_published_date: str,
    num_results: int = DEFAULT_RESULTS_PER_QUERY,
    timeout: float = 12.0,
) -> list[_ExaResult]:
    payload = {
        "query": query,
        "type": "neural",
        "numResults": num_results,
        "startPublishedDate": start_published_date,
        "useAutoprompt": True,
        "contents": {
            "text": {"maxCharacters": 1500, "includeHtmlTags": False},
            "highlights": {"numSentences": 3, "highlightsPerUrl": 2},
        },
    }
    headers = {
        "x-api-key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{EXA_BASE_URL}/search",
                json=payload,
                headers=headers,
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ExaServiceError(f"Exa HTTP error: {exc}") from exc

    data = response.json() if response.content else {}
    raw_results = data.get("results") or []
    parsed: list[_ExaResult] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        parsed.append(
            _ExaResult(
                title=str(item.get("title") or "").strip(),
                url=str(item.get("url") or "").strip(),
                published_date=item.get("publishedDate"),
                text=str(item.get("text") or "").strip(),
                highlights=[str(h).strip() for h in (item.get("highlights") or []) if h],
            )
        )
    return parsed


def _dedup_by_url(*batches: Iterable[_ExaResult]) -> list[_ExaResult]:
    seen: set[str] = set()
    merged: list[_ExaResult] = []
    for batch in batches:
        for item in batch:
            if not item.url or item.url in seen:
                continue
            seen.add(item.url)
            merged.append(item)
    return merged


def _result_mentions(item: _ExaResult, needle: str) -> bool:
    """True if the title, text, or any highlight contains ``needle``.

    Exa's neural search will happily return tangentially-related stories when
    a ticker is a typo (or something like ``ZZZZZ_FAKE_999`` that just looks
    like a stock symbol). Filtering on actual mentions keeps the pitch from
    speaking confidently about a stock that nobody is actually writing about.
    """

    needle_lower = needle.lower()
    if not needle_lower:
        return False
    pool = " ".join(
        [item.title or "", item.text or "", " ".join(item.highlights or [])]
    ).lower()
    return needle_lower in pool


def _filter_relevant(results: list[_ExaResult], ticker: str) -> list[_ExaResult]:
    if not results:
        return results
    filtered = [r for r in results if _result_mentions(r, ticker)]
    return filtered


def _build_corpus(results: list[_ExaResult]) -> str:
    lines: list[str] = []
    for idx, r in enumerate(results, start=1):
        bits: list[str] = []
        if r.title:
            bits.append(f"[{idx}] {r.title}")
        if r.published_date:
            bits.append(f"published {r.published_date[:10]}")
        if r.highlights:
            bits.append(" / ".join(r.highlights))
        elif r.text:
            bits.append(r.text[:400])
        lines.append(" — ".join(b for b in bits if b))
    return "\n".join(lines)


def _sources_payload(results: list[_ExaResult], limit: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in results[:limit]:
        out.append(
            {
                "title": r.title,
                "url": r.url,
                "publishedDate": r.published_date,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Classifiers
# ---------------------------------------------------------------------------


_LLM_INSTRUCTIONS = (
    "You are the research subagent for a personal investment assistant. "
    "Given the ticker and a list of recent news highlights from the last "
    "{days} days, return STRICT JSON with these fields: "
    "news_summary (ONE plain-English sentence, no markdown, max 220 characters), "
    "earnings_sentiment (one short sentence, mention beat/miss or guidance if any), "
    "analyst_tone (exactly one of: bullish, neutral, bearish), "
    "conviction_signal (float 0.0-1.0, where 1.0 is very high conviction). "
    "Be honest. If the corpus is light, off-topic, or does not actually mention "
    "the ticker, lean toward neutral and around 0.5 conviction. Do not invent "
    "prices, numbers, or events that are not in the corpus."
)


async def _classify_with_llm(
    *, ticker: str, corpus: str, days: int
) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not corpus.strip():
        return None
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return None

    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": _LLM_INSTRUCTIONS.format(days=days),
                },
                {
                    "role": "user",
                    "content": (
                        f"Ticker: {ticker}\n"
                        f"Recent corpus (most relevant first):\n{corpus}\n"
                        f"Return JSON only."
                    ),
                },
            ],
        )
    except Exception as exc:  # noqa: BLE001 - keep the demo loop alive
        logger.warning("Exa classifier (LLM) failed: %s", exc)
        return None

    try:
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
    except (AttributeError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("Exa classifier returned non-JSON: %s", exc)
        return None

    return _shape_classification(parsed)


def _shape_classification(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {}
    summary = str(parsed.get("news_summary") or "").strip()
    earnings = str(parsed.get("earnings_sentiment") or "").strip()
    tone_raw = str(parsed.get("analyst_tone") or "").strip().lower()
    tone = tone_raw if tone_raw in {"bullish", "neutral", "bearish"} else "neutral"
    try:
        conviction = float(parsed.get("conviction_signal", 0.5))
    except (TypeError, ValueError):
        conviction = 0.5
    return {
        "news_summary": summary,
        "earnings_sentiment": earnings,
        "analyst_tone": tone,
        "conviction_signal": max(0.0, min(1.0, conviction)),
    }


def _classify_heuristically(*, ticker: str, results: list[_ExaResult]) -> dict[str, Any]:
    if not results:
        return {
            "news_summary": (
                f"No fresh Exa coverage surfaced for {ticker} this week — "
                "treat the take below as low-conviction context."
            ),
            "earnings_sentiment": "Unknown — no recent earnings-flavoured stories were retrieved.",
            "analyst_tone": "neutral",
            "conviction_signal": 0.45,
        }

    bullish = bearish = 0
    blob_parts: list[str] = []
    for r in results:
        lower = (" ".join(r.highlights) or r.text).lower()
        for term in _BULLISH_TERMS:
            if term in lower:
                bullish += 1
        for term in _BEARISH_TERMS:
            if term in lower:
                bearish += 1
        if r.highlights:
            blob_parts.extend(r.highlights[:1])
        elif r.text:
            blob_parts.append(r.text[:160])

    blob = " ".join(blob_parts)
    blob = re.sub(r"\s+", " ", blob).strip()
    if len(blob) > 240:
        blob = blob[:237].rstrip(",;:- ") + "..."

    if bullish - bearish >= 2:
        tone = "bullish"
        conviction = min(0.85, 0.55 + 0.05 * (bullish - bearish))
    elif bearish - bullish >= 2:
        tone = "bearish"
        conviction = max(0.2, 0.5 - 0.05 * (bearish - bullish))
    else:
        tone = "neutral"
        conviction = 0.55

    earnings_blob = next(
        (
            r.highlights[0]
            for r in results
            if r.highlights
            and re.search(r"earning|guidance|revenue|EPS", r.highlights[0], re.IGNORECASE)
        ),
        "",
    )
    if earnings_blob:
        if len(earnings_blob) > 160:
            earnings_blob = earnings_blob[:157].rstrip() + "..."
        earnings_sentiment = earnings_blob
    else:
        earnings_sentiment = (
            "No earnings-specific commentary in this batch; treat earnings stance as unknown."
        )

    summary = blob or (
        f"Recent {ticker} coverage surfaced from Exa, but the highlights are sparse — "
        "context below is best-effort."
    )

    return {
        "news_summary": summary,
        "earnings_sentiment": earnings_sentiment,
        "analyst_tone": tone,
        "conviction_signal": conviction,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _start_date(days: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%S.000Z")


async def search(ticker: str, days: int = 7) -> dict[str, Any]:
    """Return research bundle for ``ticker`` based on Exa neural search.

    The shape is what ``app.agents.research._normalize_research`` expects,
    plus a ``sources`` field for UI / sponsor narrative use.
    """

    normalized = ticker.upper().strip()
    cache_key = f"{normalized}:{days}"
    now = time.time()

    cached = _cache.get(cache_key)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise ExaServiceError("EXA_API_KEY is not set")

    start_date = _start_date(days)
    queries = [
        f"{normalized} stock news analyst commentary {datetime.now(timezone.utc).year}",
        f"{normalized} earnings results guidance margins demand",
    ]

    try:
        batches = await asyncio.gather(
            *[
                _exa_search(
                    api_key=api_key,
                    query=q,
                    start_published_date=start_date,
                )
                for q in queries
            ],
            return_exceptions=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise ExaServiceError(f"Exa gather failed: {exc}") from exc

    deduped: list[_ExaResult] = []
    errors: list[str] = []
    for batch in batches:
        if isinstance(batch, Exception):
            errors.append(str(batch))
            continue
        deduped = _dedup_by_url(deduped, batch)

    if not deduped and errors:
        raise ExaServiceError("; ".join(errors))

    relevant = _filter_relevant(deduped, normalized)
    if not relevant:
        # Exa returned stories but none mention this ticker — likely a typo /
        # fake symbol. Refuse to confidently summarize.
        raise ExaServiceError(
            f"Exa returned no stories that mention {normalized} in the last {days} days"
        )

    corpus = _build_corpus(relevant)
    classified = await _classify_with_llm(ticker=normalized, corpus=corpus, days=days)
    if not classified:
        classified = _classify_heuristically(ticker=normalized, results=relevant)
    elif not classified.get("news_summary"):
        # The model returned valid JSON but an empty summary — re-fill from heuristic
        # so the synthesis layer still has something concrete.
        fallback = _classify_heuristically(ticker=normalized, results=relevant)
        classified["news_summary"] = fallback["news_summary"]

    payload = {
        **classified,
        "sources": _sources_payload(relevant),
    }
    _cache[cache_key] = (now, payload)
    return payload


def clear_cache() -> None:
    _cache.clear()
