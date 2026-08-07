# The Interview Agent

An AI agent that conducts a personalized, multi-turn technical interview based on a
candidate's actual progress through **The AI Cohort** (31-day AI engineering program),
and produces structured feedback at the end. Built to the API contract in
`technical-spec.md`.

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

That's it — the server runs fully self-contained, with no required external services.
By default it tries to enhance question phrasing with Google's free-tier Gemini API;
if no API key is configured (or the call fails for any reason), it transparently uses
a deterministic rule-based engine instead (see [LLM layer](#llm-layer--fallback) below).
No paid API key of any kind is required.

### Optional: enable LLM-generated phrasing via Gemini (free tier)

```bash
# 1. Go to https://aistudio.google.com/apikey
# 2. Sign in with a Google account, click "Create API key" -- no credit card required
# 3. Set it as an environment variable (never commit it):
export GEMINI_API_KEY="your-key-here"
```

Configure via environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | *(unset)* | Free API key from Google AI Studio. Without it, the agent runs on the fallback engine. |
| `GEMINI_MODEL` | `gemini-flash-latest` | Which free-tier-eligible Gemini model to call |

On a hosted platform (e.g. Render), set `GEMINI_API_KEY` in the dashboard's Environment
settings rather than in code -- it's never read from anywhere but the environment.

## API

Single endpoint, matching `technical-spec.md` exactly:

```
POST /api/interview
```

**Start an interview:**
```json
{ "sessionId": "abc-123", "candidate": { "member": {...}, "missions": [...], "signals": {...} } }
→ { "reply": "Hi Sarah! ... Let's start with Day 7 — Embeddings Explained. ...", "done": false }
```

**Continue it:**
```json
{ "sessionId": "abc-123", "message": "We used cosine similarity over OpenAI embeddings..." }
→ { "reply": "Interesting — what would you do if two very different chunks scored highly similar?", "done": false }
```

**Completion:**
```json
{ "reply": "Thanks for walking me through all of that -- interview completed.", "done": true,
  "feedback": { "summary": "...", "strengths": [...], "gaps": [...], "next": [...] } }
```

`candidate` is expected to follow `candidates.json`'s per-entry shape (`{member, missions,
signals}`), but the endpoint also accepts the whole `candidates.json` wrapper (uses the
first entry) or a flattened member object, so a minor client mismatch doesn't break the
flow (see [Robustness](#robustness--edge-cases-handled)).

## How the interview is personalized

1. **`app/interview/planner.py`** reads the candidate's `missions[]` and buckets each one:
   - **mastered** — passed on the first attempt → asked a *harder* question (tradeoffs,
     edge cases, "what breaks at 100x scale").
   - **shaky** — passed only after multiple attempts → asked to explain the concept in
     their own words, to check whether they actually understood it or just muscled through.
   - **struggled** — mission explicitly failed (`passed: false`) → asked a gentle,
     fundamentals-first question.
   - **skipped** — mission skipped entirely → asked an awareness-level question rather
     than assuming any mastery.

   It then builds a plan of up to 6 topics, deliberately mixing categories (strong topics,
   weak topics, skipped topics) so the interview probes both depth and gaps rather than
   only the candidate's best material. If a candidate's mission log is too sparse to reach
   4 distinct days (e.g. a candidate who skipped most of the cohort), the plan pads out
   with well-known, widely-covered curriculum days framed as general questions — so **every
   interview still covers at least 4 distinct days**, satisfying the spec's minimum
   regardless of how incomplete the candidate's data is.

2. **Each topic runs as a main question + one adaptive follow-up** (`app/interview/engine.py`),
   so a 6-topic plan produces **12 questions across 6 days** — well above the "minimum 8
   questions across 4 days" requirement, with margin for sparse or edge-case profiles.
   The follow-up is generated *from the candidate's actual answer*: vague or very short
   answers get a simpler, more concrete follow-up (never piling on difficulty when someone
   is already stuck); strong, specific answers get pushed deeper (tradeoffs, failure
   modes, "how would this change at scale").

3. **Feedback** is synthesized from the full transcript at the end, citing specific days
   and topics rather than generic praise/criticism.

## LLM layer & fallback

`app/interview/llm.py` calls Google's free-tier Gemini API (`gemini-flash-latest` by default)
for natural-sounding question and follow-up phrasing and for the final feedback
synthesis. Every call is wrapped so that **any** failure — no API key configured, a
network error, a safety block, a rate limit, malformed JSON, or a timeout — falls
straight through to `app/interview/fallback.py`, a deterministic engine that:

- Still adapts question *depth* to the candidate's mastery signal per topic.
- Still adapts the *follow-up* to whether the previous answer was vague/short vs.
  substantive (using simple heuristics instead of an LLM judgment call).
- Still produces well-formed `{summary, strengths, gaps, next}` feedback derived from the
  transcript.

This means the agent **never 500s, hangs, or produces a broken interview because of an
LLM outage** — it degrades to templated-but-still-adaptive behavior instead.

## Robustness / edge cases handled

- **No candidate data / sparse mission log** → plan pads with generic curriculum days;
  never fewer than 4 distinct days.
- **Alternate candidate payload shapes** → accepts `{member, missions, signals}` (per
  spec), the full `candidates.json` `{candidates: [...]}` wrapper, or a flattened
  top-level member object.
- **Unrecognized candidate shape** → `422` with a clear message, not a crash.
- **Missing `sessionId`, or both `candidate` and `message` absent** → `422`.
- **`message` sent for an unknown/expired `sessionId`** → `404` with a message telling
  the client to start over, rather than a stack trace.
- **Empty/whitespace-only answer** → the agent asks the candidate to share at least a
  partial thought; after two consecutive empty answers on the same question it moves on
  rather than getting stuck in a loop.
- **Messages sent after the interview is already `done`** → returns the cached feedback
  again (idempotent), never recomputes or errors.
- **Restarting mid-interview** → sending a new `candidate` payload on an in-progress
  `sessionId` cleanly restarts that session rather than corrupting state.
- **LLM unavailable or misbehaving** → see [LLM layer & fallback](#llm-layer--fallback).
- **CORS** enabled permissively so any frontend (the spec leaves this open) can call the
  endpoint directly from a browser during a demo.

## Project layout

```
app/
  main.py                    FastAPI app, single POST /api/interview endpoint
  data/
    curriculum.json          Provided 31-day curriculum
    candidates.json          Provided sample candidate profiles
  interview/
    curriculum.py            Loads + indexes curriculum.json by day
    planner.py                Builds the personalized question plan
    state.py                  In-memory session store (sessionId -> Session)
    engine.py                  Interview state machine (main -> followup -> next topic -> feedback)
    llm.py                    Gemini API integration
    data.py                    Loads candidates.json for the browser UI's picker
    fallback.py                Deterministic template engine (used when Gemini is unavailable)
```

## Known limitations

- Session state is in-memory and per-process — matches the spec ("no persistent user
  accounts" required), but a restart of the server clears all in-progress interviews.
  Fine for the scope of this challenge; would move to Redis/DB for a multi-instance
  production deployment.
- Concurrent requests against the *same* `sessionId` are not fully serialized beyond a
  coarse store-level lock — acceptable for a single interviewer conversation, which is
  inherently sequential.
