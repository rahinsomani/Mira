"""Glanceable web UI for the mirror screen. Run standalone with:
    uvicorn mira.display.server:app --reload

In the real system this is fed by orchestrator.py after each voice turn;
`latest_state` is a placeholder for that hand-off (replace with a proper
pub/sub or shared store once more than one process needs it)."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Mira Display")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

latest_state = {
    "glucose_value": "--",
    "trend": "steady",
    "response_text": "",
}


def update_display(glucose_value: str, trend: str, response_text: str) -> None:
    latest_state.update(
        glucose_value=glucose_value,
        trend=trend,
        response_text=response_text,
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, **latest_state})
