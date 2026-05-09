# PitchSnap — CLAUDE.md

Personalized stock-fit assistant. User onboards with a selfie + voice sample → gets a stylized avatar → types a ticker → multi-agent pipeline scores the stock against their profile → avatar speaks the verdict in their cloned voice.

**Key demo beat (Adaption track, $1,500 cash):** 👎 "too jargon-y" → next pitch is audibly simpler → StyleProfilePanel updates live. Do not cut this.

---

## How to Run

**Three servers run in parallel:**

```bash
# Terminal 1 — Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in API keys first
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Convex (real-time DB)
cd frontend
npx convex dev   # authenticates, creates convex/_generated/

# Terminal 3 — Frontend
cd frontend
npm run dev      # opens http://localhost:5173
```

**Phase 1 checkpoint:** Open http://localhost:5173/dashboard → type NVDA → see hardcoded pitch JSON + score card on screen. No API keys needed yet.

---

## Architecture

```
React + Vite (frontend/)          FastAPI (backend/)
  /dashboard                        POST /pitch      → orchestrator
  /onboarding                       POST /onboard    → GPT Image 2 + ElevenLabs clone
  /history                          POST /feedback   → Adaption update
                                    GET  /profile/{id} → Adaption get
                                    WS   /realtime   → GPT Realtime 2 proxy

Convex (convex/)                  External APIs
  users table                       OpenAI GPT-5.5   orchestrator + subagents
  pitches table                     OpenAI Image 2   avatar generation
  feedback table                    OpenAI Realtime 2 live voice
                                    ElevenLabs       voice clone + TTS + LipSync
                                    Exa              semantic news search
                                    Smithery MCP     market data (price, P/E, beta…)
                                    Adaption         user style profile (adaptive data)
```

---

## Build Status

| Phase | What | Status |
|-------|------|--------|
| 1 | Skeleton — mock routes, Convex schema, routing, PitchCard, TickerInput | ✅ Done |
| 2 | Real agent loop — orchestrator + research, valuation, fit score, synthesis | 🟡 In progress — backend pipeline works; valuation now pulls real FMP stable API data when Smithery cannot pass FMP token |
| 3 | Personalization — Adaption service, POST /feedback, FeedbackButtons, StyleProfilePanel live | ⬜ |
| 4 | Avatar pipeline — OnboardingFlow, GPT Image 2, ElevenLabs clone+TTS, AvatarViewport | ⬜ |
| 5 | Realtime voice + polish — GPT Realtime 2 WS proxy, share button, pre-seed kai_demo | ⬜ |

---

## Phase 2 — What to Build Next (Dev A)

Goal: replace mock routes with real agent calls. Checkpoint: NVDA returns real news, real fit score, real pitch text.

### Current Phase 2 Status — 2026-05-09

**Implemented locally and tested:**
- `backend/app/agents/orchestrator.py` calls `research → valuation → fit_score → synthesis`.
- `backend/app/agents/research.py` exists with deterministic fallback research. It will use `app.services.exa_service.search(ticker, days=7)` once that service exists.
- `backend/app/agents/valuation.py` exists with fallback valuation data and calls `app.services.smithery_service.get_fundamentals(ticker)` when available.
- `backend/app/agents/fit_score.py` computes the weighted score deterministically.
- `backend/app/agents/synthesis.py` creates the spoken pitch and now consumes richer valuation/report context when present.
- `backend/app/routes/pitch.py` now calls `run_orchestrator(...)` instead of returning the old `MOCK_PITCH`.
- `/pitch` smoke test passes for NVDA/TSLA with fallback data.

**Smithery integration code added locally:**
- `backend/app/services/smithery_service.py` calls Smithery Connect API from `.env`.
- Uses 5-minute ticker cache.
- Working Smithery connector for sponsor track: `shibui/finance` with connection ID `finance`.
- Shibui tools used: `stock_data_query` (and schema/pattern tools for development). It returns live Smithery-backed price, P/E, market cap, 3-month momentum, sector tags, and growth/quality context.
- Core FMP tools: `getQuote`, `getCompanyProfile`, `getFinancialRatiosTTM`, `getKeyMetricsTTM`, `getPriceTargetConsensus`, `getStockPriceChange`.
- Optional report-context tools: `getRatingsSnapshot`, `getStockGradeSummary`, `getAnalystEstimates`, `getEarningsReports`, `getIncomeStatementGrowth`, `getFinancialScores`, `getStockPeers`, `getSectorPESnapshot`, `getIndustryPESnapshot`.
- Normalizes output into valuation fields plus `analyst_context`, `earnings_context`, `quality_context`, and `peer_context`.

**Current Smithery/FMP status — KNOWN ISSUE:**
- Smithery namespace `tkzk2003` has two FMP connectors: `cfocoder-financial-modeling-prep-mcp-server` and `imbenrabi-financial-modeling-prep-mcp-server`. Both show status connected and expose 253 tools.
- **Both connectors fail tool calls** with `FMP_ACCESS_TOKEN is required for this operation`. Root cause: the Smithery Connect UI does not present a config schema for these servers, so `FMP_ACCESS_TOKEN` is never injected. This is a Smithery-side issue, not a code bug.
- Smithery namespace also has working connector `shibui/finance` with connection ID `finance`; its `stock_data_query` succeeds through Smithery Connect and should be used for sponsor-track proof.
- `FMP_ACCESS_TOKEN` is present in `.env` — the direct FMP stable API call works fine.
- **`smithery_service.py` now tries Shibui/Smithery first, then tries FMP/Smithery, then falls back to direct FMP on any `SmitheryServiceError`, `httpx.HTTPStatusError`, or `httpx.RequestError`**. The fallback is broad — the demo will never break regardless of Smithery state.
- `/pitch` smoke test for NVDA returns real FMP values: live price, market cap, beta, analyst target, EPS, momentum, peer context.
- For the demo: narrate that Smithery MCP is connected and successful Shibui tool calls provide valuation context; FMP enriches missing fields and protects against connector token issues.
- **If you want a working Smithery call**: search Smithery for a market-data connector that (a) has a visible config schema in the setup UI, or (b) works without an external API key.

**All Phase 2 agent files are committed and working. `/pitch` is live.**

### Files to create

**`backend/app/agents/orchestrator.py`**
- GPT-5.5 (`gpt-4.5-preview` or latest) with function calling
- Calls tools in order: `research` → `valuation` → `fit_score` → `synthesize`
- Loads user style profile from `profile.KAI_DEMO_PROFILE` (hardcoded until Phase 3)
- System prompt: `backend/app/prompts/orchestrator.md`

**`backend/app/agents/research.py`**
- Uses `exa_service.search(ticker, days=7)` 
- Returns `{ news_summary, earnings_sentiment, analyst_tone, conviction_signal: 0–1 }`
- System prompt: `backend/app/prompts/research.md`

**`backend/app/agents/valuation.py`**
- Uses `smithery_service.get_fundamentals(ticker)`
- Returns `{ price, pe_trailing, pe_forward, eps, market_cap, beta, consensus, momentum_3m }`
- System prompt: `backend/app/prompts/valuation.md`

**`backend/app/agents/fit_score.py`**
- Pure computation (no LLM needed):
  ```
  total = 0.40*risk_fit + 0.25*style_fit + 0.15*horizon_fit + 0.20*conviction
  risk_fit    = (1 - |user_tolerance - stock_beta_norm|) * 10
  style_fit   = thematic overlap score (user interests vs sector tags)
  horizon_fit = growth/value vs user horizon classification
  conviction  = research.conviction_signal * 10
  ```
- Returns breakdown JSON with score (0–10) + one-line reason per component
- System prompt: `backend/app/prompts/fit_score.md`

**`backend/app/agents/synthesis.py`**
- GPT-5.5, conditioned on user style profile
- Output: 60–90 word spoken pitch, natural cadence, no markdown
- System prompt: `backend/app/prompts/synthesis.md` (injects profile values at call time)

**`backend/app/services/exa_service.py`**
```python
# IMPORTANT: cache per ticker in module-level dict with 5-min TTL
# NVDA must not make a fresh Exa call on every demo run
_cache: dict[str, tuple[float, dict]] = {}  # ticker → (timestamp, result)
```

**`backend/app/services/smithery_service.py`**
- Same caching pattern as exa_service
- Smithery MCP HTTP API

**`backend/app/services/convex_service.py`**
- HTTP wrapper around Convex HTTP API for server-side mutations
- Methods: `save_pitch(userId, ticker, fitScore, breakdown, spokenText)`

### Wire into `backend/app/routes/pitch.py`
Replace the hardcoded mock with:
```python
from app.agents.orchestrator import run_orchestrator
from app.routes.profile import KAI_DEMO_PROFILE  # swap for adaption_service in Phase 3

@router.post("/pitch", response_model=PitchResponse)
async def pitch(req: PitchRequest):
    profile = KAI_DEMO_PROFILE.model_dump()
    result = await run_orchestrator(req.ticker, profile)
    # TODO Phase 3: save to Convex via convex_service
    return result
```

---

## Phase 3 — Personalization Loop (both devs)

**The most important phase for demo day.**

### Dev A

**`backend/app/services/adaption_service.py`**
```python
class AdaptionService:
    BASE = "https://api.adaption.ai"  # confirm URL from Adaption docs

    async def get_profile(self, user_id: str) -> dict:
        # GET /profiles/{user_id}  with ADAPTION_API_KEY

    async def update_profile(self, user_id: str, patch: dict) -> dict:
        # PATCH /profiles/{user_id}
```

**`backend/app/routes/feedback.py`** — apply update rules:
```python
# too_jargony  → jargon_tolerance.level -= 0.08 (floor 0.1)
#               → add offending terms to unknown_or_flagged
# too_basic    → jargon_tolerance.level += 0.08 (ceiling 1.0)
# nailed_it    → append to feedback_history
```

**Inject style profile into subagents:**
Every subagent system prompt prepends (already templated in `synthesis.md`):
```
You are speaking to a user with the following profile:
- Formality: {formality}
- Jargon tolerance: {jargon_level} — avoid: {unknown_or_flagged}
- Tone style: {slang_examples}
- Preferred framing: {preferred_framing}
- Explanation depth: {explanation_depth}
Write your output exactly in this voice.
```

### Dev B

**`StyleProfilePanel.tsx`** (already scaffolded in `frontend/src/components/`)
- Currently fetches from `GET /profile/{userId}` on mount + after feedback
- Phase 3: switch to Convex live subscription once backend updates `styleProfileSummary` on Convex users table after each feedback

**`FeedbackButtons.tsx`** (already scaffolded)
- Already wired to `POST /feedback`
- Pass `refreshKey` up to Dashboard → into StyleProfilePanel to trigger re-fetch

---

## Phase 4 — Avatar Pipeline (Dev B primary)

### Onboarding flow (`frontend/src/pages/Onboarding.tsx`)
1. Selfie upload: `<input type="file" accept="image/*">` → preview
2. 30s voice recording: `MediaRecorder` API, countdown timer, playback
3. 4-question quiz: risk tolerance (slider), horizon (select), experience (select), interests (multi-select)
4. Submit → `POST /onboard` (multipart/form-data with selfie + audio + quiz JSON)
5. Show 3 avatar variants → user picks one → save to Convex

### Backend (`backend/app/routes/onboard.py`)
1. `gpt_image_service.generate_avatar(selfie_bytes, quiz)` → 3 URLs
2. `elevenlabs_service.clone_voice(audio_bytes, user_id)` → voice_id
3. Save to Convex: `{ userId, avatarImageUrl, voiceId, portfolio, ... }`

### `backend/app/services/gpt_image_service.py`
```python
# OpenAI Images API — model: "gpt-image-1" (GPT Image 2)
# Prompt: "Stylized Pixar-ish cartoon, head-and-shoulders portrait.
#   Over-ear headphones, glowing GPU chip floating beside,
#   circuit-board patterns on clothing.
#   Dark gradient background. Not photorealistic. 1024x1024."
# Generate n=3 variants. Use selfie as reference image.
```

### `backend/app/services/elevenlabs_service.py`
```python
# IMPORTANT: check Convex users table for existing voice_id before cloning.
# Never re-clone for the same user_id — costs credits and is slow.
from elevenlabs.client import ElevenLabs

async def clone_voice(audio_bytes, user_id) -> str:
    # client.clone(name=f"{user_id}_voice", files=[audio_bytes])
    # returns voice.voice_id → save to Convex

async def generate_speech(text, voice_id) -> bytes:
    # client.generate(text=text, voice=voice_id, model="eleven_multilingual_v2")
    # MOCK THIS during dev — only call real API in final 4 hours

async def generate_lipsync(audio_url, avatar_image_url) -> str | None:
    # ElevenLabs LipSync API (OmniHuman 1.5) → returns MP4 URL
    # Returns None on failure — AvatarViewport falls back to static image + glow
```

---

## Phase 5 — Realtime Voice + Polish

### Dev A: `backend/app/routes/realtime.py`
```python
# WebSocket proxy to GPT Realtime 2
# wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview
# System prompt: investment twin, last pitch context, style profile
# Bi-directional: client PCM audio → OpenAI → PCM back to client
# System prompt template:
#   "You are the user's personal investment twin. You have just delivered
#    a pitch on {ticker} with fit score {score}.
#    User style profile: {profile_summary}
#    Respond conversationally. Under 4 sentences. Jargon level: {jargon_level}"
```

### Dev B: `frontend/src/hooks/useRealtimeVoice.ts`
- `getUserMedia` → PCM streaming over WebSocket to `/realtime`
- Incoming audio → Web Audio API playback
- Exposes `{ isActive, isListening, isSpeaking, toggle }`

### Pre-seed `kai_demo` before demo day
Run this in `frontend/convex/seed.ts` (or a one-off script):
```typescript
// Insert kai_demo user
await ctx.db.insert("users", {
  userId: "kai_demo",
  displayName: "Kai",
  avatarImageUrl: "<generated avatar URL>",
  voiceId: "<elevenlabs voice_id>",
  portfolio: [
    { ticker: "NVDA", weight: 0.28, avgCost: 480 },
    { ticker: "MSFT", weight: 0.20, avgCost: 380 },
    { ticker: "AAPL", weight: 0.15, avgCost: 175 },
    { ticker: "AMD",  weight: 0.12, avgCost: 140 },
    { ticker: "TSMC", weight: 0.10, avgCost: 120 },
    { ticker: "META", weight: 0.08, avgCost: 480 },
    { ticker: "AMZN", weight: 0.07, avgCost: 175 },
  ],
  styleProfileSummary: "Casual, jargon-tolerant 55%, AI/semis focus, upside-first framing",
  createdAt: Date.now(),
});
// Also insert pre-rendered NVDA + TSLA pitches as fallback
```

### Share button
- `html2canvas` on `#pitch-{pitchId}` → download as `pitchsnap-{ticker}.png`
- Install: `npm install html2canvas`

---

## File Map

```
backend/app/
  main.py                    FastAPI app + CORS + route registration
  models/schemas.py          Pydantic models (PitchRequest, PitchResponse, FeedbackRequest, …)
  routes/
    pitch.py                 POST /pitch — Phase 1: mock; Phase 2: → orchestrator
    feedback.py              POST /feedback — Phase 1: echo; Phase 3: → adaption_service
    profile.py               GET /profile/{id} — Phase 1: hardcoded Kai; Phase 3: → adaption_service
    onboard.py               POST /onboard — Phase 1: mock; Phase 4: → gpt_image + elevenlabs
    realtime.py              WS /realtime — Phase 1: echo; Phase 5: → GPT Realtime 2 proxy
  agents/
    orchestrator.py          (Phase 2) GPT-5.5 function calling — calls 4 tools in sequence
    research.py              (Phase 2) Exa semantic search subagent
    valuation.py             (Phase 2) Smithery MCP fundamentals subagent
    fit_score.py             (Phase 2) Fit score computation (no LLM)
    synthesis.py             (Phase 2) GPT-5.5 spoken pitch writer
  services/
    exa_service.py           (Phase 2) Exa API wrapper + ticker cache
    smithery_service.py      (Phase 2) Smithery MCP wrapper + ticker cache
    convex_service.py        (Phase 2) Convex HTTP API client (server-side mutations)
    adaption_service.py      (Phase 3) Adaption user style profile get/update
    elevenlabs_service.py    (Phase 4) Voice clone + TTS + LipSync
    gpt_image_service.py     (Phase 4) GPT Image 2 avatar generation
  prompts/
    orchestrator.md          Orchestrator system prompt
    research.md              Research subagent system prompt
    valuation.md             Valuation subagent system prompt
    fit_score.md             Fit score subagent system prompt
    synthesis.md             Synthesis subagent system prompt (profile values injected at call time)

frontend/src/
  App.tsx                    React Router — /dashboard /onboarding /history + sidebar nav
  main.tsx                   ConvexProvider + React root
  index.css                  Dark theme CSS (no Tailwind)
  lib/api.ts                 Typed fetch wrappers for all backend routes
  pages/
    Dashboard.tsx            Main page — TickerInput + PitchCard + AvatarViewport + StyleProfilePanel
    Onboarding.tsx           (Phase 4) selfie + voice + quiz flow
    History.tsx              (Phase 2+) past pitches from Convex
  components/
    TickerInput.tsx           Input + submit → calls postPitch()
    PitchCard.tsx             Fit score card with breakdown bars + spoken text
    AvatarViewport.tsx        Avatar image / lipsync video / audio autoplay
    FeedbackButtons.tsx       👍/👎 buttons → POST /feedback (Phase 3: triggers adaption update)
    StyleProfilePanel.tsx     Live jargon gauge + slang tags + flagged terms
    RealtimeVoiceToggle.tsx   (Phase 5) mic button for GPT Realtime 2
  hooks/
    useConvex.ts              Typed Convex query/mutation wrapper stubs
    useRealtimeVoice.ts       (Phase 5) WebSocket + mic + audio playback

convex/
  schema.ts                  ⚠️ LOCKED after Phase 1 — do not alter (users, pitches, feedback)
  users.ts                   getUser, upsertUser, updateStyleSummary
  pitches.ts                 savePitch, getPitchesByUser, getLatestPitch
  feedback.ts                saveFeedback, getFeedbackByUser
```

---

## Fit Score Formula

```
total = 0.40 * risk_fit + 0.25 * style_fit + 0.15 * horizon_fit + 0.20 * conviction

risk_fit    = (1 - |user.risk_tolerance - stock_beta_normalized|) * 10
              stock_beta_normalized = clamp(beta / 2.0, 0, 1)
style_fit   = len(intersection(user.thematic_interests, stock_sector_tags)) / max(len(user.thematic_interests), 1) * 10
horizon_fit = 10 if user.horizon matches stock growth classification, else 5 (partial), else 2
conviction  = research.conviction_signal * 10   # 0–1 from Exa → 0–10
```

All component scores are 0–10. Final total is 0–10.

---

## User Style Profile (Adaption)

Schema stored in Adaption, cached/reflected in Convex `users.styleProfileSummary`:

```json
{
  "user_id": "kai_demo",
  "tone": { "formality": 0.25, "emoji_usage": 0.35, "slang_examples": ["lowkey", "bag", "ngl", "fam"] },
  "jargon_tolerance": { "level": 0.55, "known_terms": ["P/E", "EPS", "beta", "market cap"], "unknown_or_flagged": [] },
  "risk_language": { "tolerance": 0.72, "preferred_framing": "upside_first" },
  "explanation_depth": "medium",
  "thematic_interests": ["semiconductors", "AI infrastructure", "cloud", "consumer tech"],
  "horizon": "6_months_to_2_years",
  "feedback_history": []
}
```

**Update rules (Phase 3, `backend/app/routes/feedback.py`):**
- `too_jargony` → `jargon_tolerance.level -= 0.08` (floor 0.1), add terms to `unknown_or_flagged`
- `too_basic`   → `jargon_tolerance.level += 0.08` (ceiling 1.0)
- `nailed_it`   → append `{ ticker, score, ts }` to `feedback_history`

---

## Convex Schema (LOCKED)

Do not change after Phase 1. Adding columns requires a migration and re-deploy.

Tables: `users`, `pitches`, `feedback` — see `convex/schema.ts`.

To run Convex locally: `cd frontend && npx convex dev`

---

## Environment Variables

See `.env.example` at repo root. Copy to `.env` and fill in before Phase 2.

Backend reads from `.env` via `python-dotenv` (already in `backend/app/main.py`).
Frontend reads `VITE_*` vars from `.env` in the `frontend/` directory (or root with Vite config).

---

## Hard Rules

1. **Phase checkpoints are mandatory.** Do not start the next phase until its checkpoint passes.
2. **Adaption personalization loop is non-negotiable** — the 👎 → simpler pitch demo beat wins $1,500 cash. Do not cut it.
3. **Avatar lipsync is nice-to-have.** If Phase 4 runs long, ship audio + static image + CSS glow (`avatar-glow` class already in `index.css`). Demo still lands.
4. **Pre-render NVDA + TSLA pitches** as fallback in Convex the morning of demo day. Never rely solely on a live render.
5. **Cache market data per ticker** — see `exa_service.py` + `smithery_service.py`. 5-minute TTL. NVDA must not re-call Exa on every demo run.
6. **Convex schema is locked after Phase 1.** No schema alterations mid-build.
7. **Mock ElevenLabs TTS during dev.** Only call real TTS endpoint in the final 4 hours.
8. **Clone voice once, save voice_id, reuse.** Check Convex users table for existing `voiceId` before calling ElevenLabs clone API.
9. **Update this file after meaningful architecture/API changes.** Future agents should be able to read `CLAUDE.md` and know what was built, what is fallback-only, what is blocked, and how to verify it.

---

## Sponsor Track Checklist

| Track | What to call out in demo |
|-------|--------------------------|
| OpenAI GPT-5.5 + Codex | Show orchestrator calling 4 tools in sequence (research → valuation → fit_score → synthesize) |
| OpenAI GPT Realtime 2 | Toggle voice mode → interrupt avatar mid-pitch: "wait, what's beta?" |
| OpenAI GPT Image 2 | Avatar generation during onboarding — show 3 variants, user picks one |
| Adaption — 1st ($1,500) | 👎 too jargon-y → TSLA pitch → StyleProfilePanel jargon gauge drops live |
| Convex | StyleProfilePanel updates via live Convex subscription (no polling) |
| Exa — Most Creative | Research subagent pulling 7-day news + earnings sentiment semantically |
| Smithery — Most Connectors | Valuation subagent using multiple MCP connectors (price, P/E, beta, consensus) |
