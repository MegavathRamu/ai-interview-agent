# AI Usage Log

This project was built with **Claude Code** (Sonnet 5) as an interactive pair-programming
assistant across a single working session. This log documents what was AI-assisted, the
key decisions and steering that shaped the implementation, and what was reviewed/directed
by a human at each step.

## Session summary

| Stage | What happened |
|---|---|
| 1 | Provided the three challenge resources (`curriculum.json`, `candidates.json`, `technical-spec.md`) and asked Claude to read and understand all three fully before implementing anything. |
| 2 | Claude read all three files end-to-end, summarized the API contract, curriculum structure, and the range of candidate profiles (including edge cases like near-zero mission completion and explicit mission failures) back to confirm understanding before writing code. |
| 3 | Claude proposed and built a FastAPI service implementing the `POST /api/interview` contract, including a personalization engine that classifies each candidate's missions (mastered / shaky / struggled / skipped) and builds a diverse question plan from them. |
| 4 | Claude's first LLM-integration draft used the Anthropic Claude API (`claude-opus-5`) for question/follow-up/feedback generation. **Human steering:** flagged that the company-provided subscription only covers the Claude Code product, not a separate billed API key, and asked for an alternative. |
| 5 | Claude proposed options (local Ollama model / no-LLM deterministic fallback / a different provider's API / user's own Anthropic key) via a clarifying question; human chose **local Ollama**, noting it also fits the cohort's own Day 2 curriculum (Ollama + Qwen2.5-Coder setup). |
| 6 | Claude rewrote the LLM integration layer to call a local Ollama server via stdlib HTTP calls (no new dependency), keeping the previously-built deterministic fallback engine as a safety net for when Ollama is unavailable. |
| 7 | Human asked how to manually test the running server; Claude provided copy-pasteable `curl` commands using real sample candidates from `candidates.json`. |
| 8 | Human asked Claude to install Ollama and pull `llama3.1` to enable LLM-generated phrasing. Claude installed Ollama via Homebrew and started the background service. **Human steering:** stopped Claude before the ~4.7GB model download, citing it was a company laptop. |
| 9 | Claude explained the download size/purpose plainly on request, then asked (rather than assuming) whether to skip the LLM entirely, pull a much smaller model, or leave the decision for later. Human chose to skip Ollama entirely and rely on the already-built-and-tested deterministic fallback engine. Claude stopped the Ollama background service it had started, so nothing was left running silently on the machine. |
| 10 | Human asked for confirmation that the fallback engine works as a complete interview experience on its own (not a degraded stub). Claude confirmed based on the automated end-to-end tests already run in Stage 3-6 below. |

## What Claude generated

- All application code: `app/main.py`, and every module under `app/interview/`
  (`curriculum.py`, `planner.py`, `state.py`, `engine.py`, `llm.py`, `fallback.py`).
- `README.md`, `requirements.txt`, `.env.example`.
- The personalization logic (mission-history classification -> question plan) and the
  adaptive follow-up heuristics in the deterministic fallback engine.
- All test scripts used to verify the build (see below) -- written and executed by
  Claude, with output reviewed by the human in the terminal in real time.

## What was human-directed / reviewed

- The choice of backend framework, language, and overall architecture was Claude's
  proposal, accepted implicitly by the human proceeding without objection.
- The pivot away from the Anthropic API to Ollama, and later the pivot away from Ollama
  entirely to the deterministic fallback engine, were both **human decisions** made in
  response to real constraints (company subscription scope, company laptop policy) --
  not something Claude decided unprompted. Claude's role at each pivot was to explain
  trade-offs and implement the human's choice, not to choose for them.
- All test runs (see below) were executed by Claude in the terminal but their pass/fail
  output was visible to and reviewed by the human in the conversation transcript.

## Automated testing performed during the build

Run directly against the live FastAPI server via HTTP, before any human-facing claim of
"it works" was made:

- Full interview simulations end-to-end for multiple sample candidates (a struggling
  profile with many failed/skipped missions, and a strong first-try-pass profile),
  confirming: correct question count (12 across 6 topics, exceeding the 8-question/
  4-day minimum), correct adaptation to mission-history category, correct adaptive
  follow-ups to vague vs. substantive answers, and well-formed structured feedback on
  completion.
- Edge cases: unknown `sessionId` on a turn request (404), missing `sessionId` /
  missing both `candidate` and `message` (422), malformed/unrecognized candidate
  payload shapes (422), the full `candidates.json` wrapper shape and a flattened
  member-object shape both normalizing correctly, a zero-mission candidate still
  producing a >=4-day plan via generic-day padding, empty/whitespace answers being
  handled without crashing or infinite-looping, messages sent after interview
  completion returning the cached feedback idempotently, and restarting an
  in-progress session by sending a new `candidate` payload.
- Verified the planner produces >=4 distinct curriculum days for all 20 sample
  candidates in `candidates.json`, including the sparsest profile (5 non-skipped
  missions).

## Tooling

- **Assistant:** Claude Code (model: Claude Sonnet 5), used interactively in a terminal
  session with file read/write/edit and bash execution tools.
- **No other AI tools** (e.g. GitHub Copilot, ChatGPT) were used in this project.
