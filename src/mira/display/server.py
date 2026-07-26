"""Mirror display server.

Serves the ambient display page and a push-to-talk endpoint. The page itself
captures the microphone (MediaRecorder) and plays back the spoken response, so
there is no native audio dependency on the Python side. Nothing is shown or
spoken until the button is pressed (Pr1: no ambient disclosure).

Visual design follows the "01 Morning" (ambient readout) and "02 Breakfast"
(meal guidance Q&A) screens from the Mira Figma prototype (file
Of0Gs8DBirwyQaxekTYEfU) — dark green palette, oversized type, a status pill,
and a spoken-quote/Q&A line. Laid out as two columns side by side (status on
the left, spoken content on the right) for a horizontal/landscape monitor
rather than the portrait mirror form factor.
"""

import base64
import os

from flask import Flask, jsonify, request

from mira import voice
from mira.orchestrator import Orchestrator

app = Flask(__name__)
_orchestrator = Orchestrator()

# Dexcom trend codes -> (label, arrow), matching the "steady →" style in the prototype.
_TREND_DISPLAY = {
    "doubleUp": ("rising fast", "↑↑"),
    "singleUp": ("rising", "↑"),
    "fortyFiveUp": ("rising", "↗"),
    "flat": ("steady", "→"),
    "fortyFiveDown": ("falling", "↘"),
    "singleDown": ("falling", "↓"),
    "doubleDown": ("falling fast", "↓↓"),
}


def _trend_display(trend_code):
    return _TREND_DISPLAY.get(trend_code, ("steady", "→"))


def _range_status(value):
    if value < 4.0:
        return "Low"
    if value > 10.0:
        return "High"
    return "In range"


_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mira</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,500;0,600;0,800;1,400&display=swap');

  * { box-sizing: border-box; }

  body {
    margin: 0;
    background: #0e1e17;
    color: #edefea;
    font-family: 'Inter', -apple-system, "Segoe UI", sans-serif;
    height: 100vh;
    overflow: hidden;
  }

  /* Landscape monitor layout: two columns side by side rather than one
     tall stack, so the wide aspect ratio is actually used. */
  .screen {
    position: relative;
    height: 100vh;
    padding: 5vh 5vw 12vh;
  }

  .view { display: none; height: 100%; }
  .view.active {
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: 6vw;
    height: 100%;
  }

  .col-left, .col-right {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-width: 0;
  }
  .col-left {
    border-right: 2px solid rgba(38, 64, 47, 0.7);
    padding-right: 6vw;
  }

  /* --- ambient view (01 Morning) --- */
  #time { font-weight: 800; font-size: clamp(48px, 6vw, 84px); letter-spacing: -2px; margin: 0; }
  #date { font-weight: 500; font-size: clamp(18px, 2vw, 28px); color: #8fa89a; margin: 8px 0 0; }

  .glucose-row { display: flex; align-items: baseline; gap: 16px; margin-top: 6vh; }
  #glucose-value { font-weight: 800; font-size: clamp(96px, 13vw, 170px); letter-spacing: -6px; margin: 0; line-height: 1; }
  #glucose-unit { font-weight: 500; font-size: clamp(20px, 2.4vw, 34px); color: #8fa89a; }

  .status-row { display: flex; align-items: center; flex-wrap: wrap; gap: 24px; margin-top: 3vh; }
  .pill {
    display: inline-flex; align-items: center; gap: 12px;
    background: #173326; border-radius: 100px; padding: 12px 24px 12px 20px;
  }
  .pill .dot { width: 14px; height: 14px; border-radius: 50%; background: #5bc08c; flex: none; }
  .pill span { font-weight: 600; font-size: clamp(18px, 1.7vw, 24px); color: #8fe3b4; white-space: nowrap; }
  #trend-text { font-weight: 500; font-size: clamp(18px, 1.8vw, 26px); color: #8fa89a; }

  #quote {
    font-style: italic; font-size: clamp(24px, 2.6vw, 38px); line-height: 1.35; color: #d6e2d9;
    max-width: 34ch; margin: 0 0 32px;
  }

  .speaking { display: flex; align-items: center; gap: 12px; visibility: hidden; }
  .speaking.active { visibility: visible; }
  .speaking .bars { display: flex; align-items: flex-end; gap: 6px; height: 40px; }
  .speaking .bars span {
    display: block; width: 8px; border-radius: 4px; background: #5bc08c;
  }
  .speaking .bars span:nth-child(1) { height: 35%; }
  .speaking .bars span:nth-child(2) { height: 65%; }
  .speaking .bars span:nth-child(3) { height: 100%; }
  .speaking .bars span:nth-child(4) { height: 75%; }
  .speaking .bars span:nth-child(5) { height: 45%; }
  .speaking .bars span:nth-child(6) { height: 85%; }
  .speaking .bars span:nth-child(7) { height: 55%; }
  .speaking .bars span:nth-child(8) { height: 30%; }
  .speaking.active .bars span { animation: bounce 0.9s ease-in-out infinite; }
  .speaking .bars span:nth-child(2n) { animation-delay: 0.15s; }
  @keyframes bounce { 0%, 100% { transform: scaleY(0.6); } 50% { transform: scaleY(1); } }
  .speaking-label { font-weight: 500; font-size: clamp(18px, 1.7vw, 24px); color: #8fa89a; }

  /* --- Q&A view (02 Breakfast) --- */
  #qa-time { font-weight: 600; font-size: clamp(28px, 3vw, 40px); letter-spacing: -1px; color: #8fa89a; margin: 0; }
  .qa-pill { margin-top: 24px; align-self: flex-start; }
  .qa-pill span { white-space: nowrap; }

  .section-label {
    font-weight: 600; font-size: clamp(16px, 1.5vw, 22px); letter-spacing: 3px; color: #8fa89a;
    text-transform: uppercase; margin: 0 0 12px;
  }
  #qa-question {
    display: inline-block; background: #16291f; border-radius: 28px;
    padding: 20px 26px; font-weight: 500; font-size: clamp(22px, 2.4vw, 32px); color: #edefea;
    margin: 0 0 40px; max-width: 32ch;
  }
  .mira-label { color: #5bc08c; }
  #qa-answer { font-size: clamp(26px, 3vw, 40px); line-height: 1.34; color: #edefea; max-width: 32ch; margin: 0 0 32px; }
  #qa-caption { font-size: clamp(16px, 1.6vw, 22px); line-height: 1.4; color: #5c7167; max-width: 32ch; margin: 0 0 24px; }

  /* --- mic control --- */
  #talk {
    position: absolute; bottom: 4vh; left: 50%; transform: translateX(-50%);
    width: 64px; height: 64px; border-radius: 50%; border: none;
    background: #173326; color: #8fe3b4; font-size: 24px; cursor: pointer;
  }
  #talk.recording { background: #c0483a; color: #edefea; }
</style>
</head>
<body>
  <div class="screen">

    <div id="ambientView" class="view active">
      <div class="col-left">
        <p id="time">{{ time }}</p>
        <p id="date">{{ date }}</p>

        <div class="glucose-row">
          <p id="glucose-value">{{ value }}</p>
          <span id="glucose-unit">mmol/L</span>
        </div>
        <div class="status-row">
          <div class="pill"><span class="dot"></span><span id="status-text">{{ status }}</span></div>
          <span id="trend-text">{{ trend_label }} {{ trend_arrow }}</span>
        </div>
      </div>

      <div class="col-right">
        <p id="quote">&ldquo;Good morning. Your glucose is {{ trend_label }}.&rdquo;</p>
        <div class="speaking" id="ambientSpeaking">
          <div class="bars"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
          <span class="speaking-label">Speaking</span>
        </div>
      </div>
    </div>

    <div id="qaView" class="view">
      <div class="col-left">
        <p id="qa-time">{{ time }}</p>
        <div class="pill qa-pill"><span class="dot"></span><span id="qa-status-text">{{ value }} {{ status }}</span></div>
      </div>

      <div class="col-right">
        <p class="section-label">You asked</p>
        <p id="qa-question"></p>

        <p class="section-label mira-label">Mira</p>
        <p id="qa-answer"></p>

        <p id="qa-caption">Asked out loud. Answered out loud. No screen to read.</p>
        <div class="speaking" id="qaSpeaking">
          <div class="bars"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
          <span class="speaking-label">Speaking</span>
        </div>
      </div>
    </div>

    <button id="talk" title="Hold to ask">&#127908;</button>
    <audio id="player" hidden></audio>
  </div>

<script>
const talkButton = document.getElementById("talk");
const ambientView = document.getElementById("ambientView");
const qaView = document.getElementById("qaView");
const ambientSpeaking = document.getElementById("ambientSpeaking");
const qaSpeaking = document.getElementById("qaSpeaking");
const player = document.getElementById("player");
const PLAYBACK_RATE = 1.25;
const RETURN_TO_AMBIENT_MS = 10000;

let recorder, chunks, returnTimer;

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  recorder = new MediaRecorder(stream);
  chunks = [];
  recorder.ondataavailable = (e) => chunks.push(e.data);
  recorder.onstop = sendRecording;
  recorder.start();
  talkButton.classList.add("recording");
}

function stopRecording() {
  if (recorder && recorder.state !== "inactive") {
    recorder.stop();
    recorder.stream.getTracks().forEach((t) => t.stop());
  }
  talkButton.classList.remove("recording");
}

async function sendRecording() {
  const blob = new Blob(chunks, { type: "audio/webm" });
  const formData = new FormData();
  formData.append("audio", blob, "audio.webm");

  const resp = await fetch("/ask", { method: "POST", body: formData });
  const data = await resp.json();

  clearTimeout(returnTimer);
  document.getElementById("qa-question").textContent = "“" + data.question_text + "”";
  document.getElementById("qa-answer").textContent = data.response_text;
  document.getElementById("qa-status-text").textContent = data.glucose_value + " " + data.glucose_status;
  ambientView.classList.remove("active");
  qaView.classList.add("active");

  if (data.audio_base64) {
    player.src = "data:audio/wav;base64," + data.audio_base64;
    player.playbackRate = PLAYBACK_RATE;
    qaSpeaking.classList.add("active");
    player.onended = () => {
      qaSpeaking.classList.remove("active");
      returnTimer = setTimeout(returnToAmbient, RETURN_TO_AMBIENT_MS);
    };
    player.play();
  } else {
    returnTimer = setTimeout(returnToAmbient, RETURN_TO_AMBIENT_MS);
  }
}

function returnToAmbient() {
  qaView.classList.remove("active");
  ambientView.classList.add("active");
}

talkButton.addEventListener("mousedown", startRecording);
talkButton.addEventListener("mouseup", stopRecording);
talkButton.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); });
talkButton.addEventListener("touchend", (e) => { e.preventDefault(); stopRecording(); });
</script>
</body>
</html>
"""


@app.route("/")
def index():
    reading = _orchestrator.glucose_store.current_reading()
    trend_label, trend_arrow = _trend_display(reading.get("trend"))
    return (
        _PAGE.replace("{{ time }}", "8:14")
        .replace("{{ date }}", "Today")
        .replace("{{ value }}", str(reading["value"]))
        .replace("{{ status }}", _range_status(reading["value"]))
        .replace("{{ trend_label }}", trend_label)
        .replace("{{ trend_arrow }}", trend_arrow)
    )


@app.route("/ask", methods=["POST"])
def ask():
    audio_file = request.files["audio"]
    question_text = voice.transcribe(audio_file.read(), audio_file.filename)
    result = _orchestrator.handle_query(question_text)
    glucose_value = result["glucose_reading"]["value"]

    try:
        audio_b64 = base64.b64encode(voice.synthesize(result["response_text"])).decode("ascii")
    except Exception:
        audio_b64 = None

    return jsonify({
        "question_text": question_text,
        "response_text": result["response_text"],
        "glucose_value": glucose_value,
        "glucose_status": _range_status(glucose_value),
        "audio_base64": audio_b64,
    })


def run():
    port = int(os.environ.get("MIRA_DISPLAY_PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
