"""Dev entrypoint: runs one mock voice turn and starts the display server."""

import uvicorn

from mira.config import settings
from mira.display.server import app
from mira.orchestrator import Orchestrator


def run_demo_turn() -> None:
    orchestrator = Orchestrator()
    response = orchestrator.handle_voice_turn(audio_bytes=b"", requester_confirmed=True)
    print(f"Mira response: {response}")


if __name__ == "__main__":
    run_demo_turn()
    uvicorn.run(app, host="0.0.0.0", port=settings.display_port)
