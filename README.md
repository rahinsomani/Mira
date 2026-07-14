# mira-system

Code scaffold for Mira (see `../CLAUDE.md` for full project context).

## Structure

```
src/mira/
├── main.py            entry point
├── orchestrator.py    wires the pieces below together
├── voice/
│   ├── stt.py         speech-to-text
│   └── tts.py         text-to-speech
├── data/
│   ├── glucose_store.py     glucose reading access
│   ├── sandbox_egvs.json    sample readings (Dexcom sandbox-shaped)
│   └── nutrition_store.py   nutrition lookup
├── llm/
│   ├── client.py       LLM client
│   └── safety.py       output safety checks (AI1)
└── display/
    └── server.py        mirror display screen
tests/
```

## Suggested ownership

| Module | Suggested owner |
|---|---|
| `llm/` |  |
| `data/` |  |
| `voice/` |  |
| `display/` |  |
