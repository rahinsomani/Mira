# mira-system

Code scaffold for Mira, the voice-first ambient smart mirror (see `../CLAUDE.md`
for full project context, requirements, and terminology rules — read that first).

This repo is split into modules so the five of us can work in parallel without
stepping on each other. Nothing here is production-ready; it's a runnable
skeleton with mocked data so you can build against a stable interface from
day one.

## Pipeline

```
voice.stt  -->  data (glucose + nutrition)  -->  llm (+ safety)  -->  voice.tts + display
```

See `orchestrator.py` for how the pieces connect.

## Suggested module ownership

Pick based on interest, not strictly the mapping below — but this is a
reasonable starting split for a team of 5:

| Module | Owns | Suggested owner |
|---|---|---|
| `src/mira/llm/` | Prompting, AI1 safety guardrails, fallback | Rahin (ML/LLM) |
| `src/mira/data/` | Glucose + nutrition data access | Shresta / Lana (glucose, CGM research) |
| `src/mira/voice/` | STT/TTS integration | open |
| `src/mira/display/` | Glanceable web UI, matches Figma prototype | Russell (HCI) |
| `docs/`, requirement traceability | Requirement IDs, MoSCoW tracking | Keneisha (requirements) |
| `src/mira/orchestrator.py` | Wiring the above together | shared / Rahin |

## Setup

```bash
cd mira-system
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in API keys
python -m mira.main
```

## Requirement-driven constraints (do not relax without team sign-off)

- **AI1**: LLM output must go through `llm/safety.py` before it reaches TTS/display.
  No medication-change responses, ever. If the safety check fails or the LLM
  is unavailable, fall back to the scripted responses in `llm/fallback.py`.
- **Pr1**: `data/glucose_store.py` must not return a glucose value without an
  explicit request context — no ambient/background disclosure.
- **P1**: voice response should begin within 3s — keep this in mind when
  choosing STT/LLM/TTS providers, and profile before swapping in real ones.
- **F2**: nutrition guidance needs to cover >=20 common foods — see the seed
  data in `data/nutrition_store.py`.

## Status

Scaffold only — mocked glucose/nutrition data, stub STT/TTS, and an LLM client
interface with no provider wired in yet. Replace stubs incrementally; keep the
module boundaries so parallel work doesn't conflict.
