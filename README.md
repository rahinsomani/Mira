# mira-system

Code scaffold for Mira: a
voice-first ambient smart mirror that shows CGM glucose readings and answers
spoken questions about glucose and food, with an LLM in the loop.

## How a request flows through the code

1. A person holds the mic button on the display page and speaks. The browser
   records audio and posts it to `/ask`.
2. `display/server.py` hands the audio to `voice.py`, which sends it to Groq
   for speech-to-text.
3. `orchestrator.py` takes the transcribed question, pulls the current
   glucose reading from `data/glucose_store.py` and (if the question mentions
   food) a match from `data/nutrition_store.py`, and passes all of it to
   `llm.py`.
4. `llm.py` calls the Groq chat model, then runs the reply through the AI1
   safety checks (medication-language filter, urgent-value override, length
   cap) before returning it.
5. `voice.py` turns the safe reply into speech (Groq TTS), and
   `display/server.py` sends both the text and the audio back to the page,
   which speaks it and shows it on screen.

## Structure

```
src/mira/
├── main.py            entry point: loads .env, starts the display server
├── config.py           tiny .env loader (no third-party dependency)
├── orchestrator.py      wires data -> llm together for one question
├── voice.py             speech-to-text + text-to-speech (Groq)
├── llm.py               LLM call + output safety checks (AI1), Groq
├── data/
│   ├── dexcom_auth.py       one-time script: run manually to do the Dexcom
│   │                        OAuth flow and print a DEXCOM_REFRESH_TOKEN
│   ├── dexcom_client.py     Dexcom API client (token refresh + fetch EGVs)
│   ├── glucose_store.py     glucose reading access; uses DexcomClient if
│   │                        Dexcom env vars are set, otherwise falls back
│   │                        to the bundled sandbox_egvs.json
│   ├── sandbox_egvs.json    sample glucose readings (Dexcom sandbox-shaped),
│   │                        used when no Dexcom credentials are configured
│   ├── nutrition_store.py   looks up mentioned foods in nutrition_data.json
│   └── nutrition_data.json  small bundled food list (carbs, glycemic impact)
└── display/
    └── server.py       Flask app: serves the mirror page (ambient glucose
                         readout + Q&A view) and the /ask voice endpoint
tests/
```

All LLM, speech-to-text, and text-to-speech calls go through Groq — one
`GROQ_API_KEY` in `.env` covers all three.

## Running it, from a clean checkout

1. **Create a virtualenv and install the package** (editable, so code edits
   take effect immediately):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Set up your `.env`:**

   ```bash
   cp .env.example .env
   ```

   Then fill in `GROQ_API_KEY` (required — get one at console.groq.com).
   The `DEXCOM_*` values are optional: leave them blank and Mira runs on the
   bundled sandbox glucose data; only fill them in if you want live Dexcom
   sandbox/production data (run `python -m mira.data.dexcom_auth` once to
   obtain `DEXCOM_REFRESH_TOKEN`).

3. **Run the app:**

   ```bash
   python -m mira.main
   ```

   This starts the Flask display server on `http://localhost:8000` (override
   with `MIRA_DISPLAY_PORT` in `.env`). Open that URL in a browser and hold
   the mic button to ask a question.

4. **Restarting after a code change:** the server doesn't auto-reload. Stop
   it with `Ctrl+C` (or `kill` the PID from `lsof -nP -iTCP:8000 -sTCP:LISTEN`
   if it's running in the background) and run `python -m mira.main` again.

## Suggested ownership

| Module | Suggested owner |
|---|---|
| `llm.py` |  |
| `data/` |  |
| `voice.py` |  |
| `display/` |  |
