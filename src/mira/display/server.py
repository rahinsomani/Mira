"""Mirror display server.

Serves the ambient display page and a push-to-talk endpoint. The page itself
captures the microphone (MediaRecorder) and plays back the spoken response, so
there is no native audio dependency on the Python side.

Pr1 vs F14: the requirements ask for both "no glucose values shown until a
valid request" (Pr1) and a passive glanceable status with no spoken command
(F14) - those conflict if "status" means the exact number. This implementation
draws the line at the number itself: the ambient view always shows a
qualitative status pill (In range / Low / High) and trend so it stays
glanceable, but the literal mmol/L value and the spoken quote are only shown
in the Q&A view, which only appears after the user has made an explicit voice
request. Confirm this split is what the team wants documented for Pr1/F14.

Visual design follows the Mira Figma prototype (Version 2): portrait
orientation for the mirror form factor, a translucent silhouette standing in
for "you see yourself in the glass", and five states of the same physical
screen -
  - ambient   : idle readout ("01 Morning")
  - qa        : answered voice question ("02 Breakfast")
  - trend     : asked-for 6h trend chart ("03 Midday"), backed by
                trend_analysis.compute() - a deterministic summary, never
                the LLM's own arithmetic (AI4)
  - alert     : severe hypo/hyperglycemia ("04 Severe low"), driven by the
                same LOW_MMOL/HIGH_MMOL thresholds llm.py already uses
  - connection: CGM data unavailable ("06 Connection"), driven by F6

Unlike the ambient view, the trend chart is only ever shown after the user
asks for it (same Pr1 request-gating as the Q&A view) - it's a full picture
of recent values, which is more disclosure than the masked ambient readout,
not less.

The accessibility-settings ("05 Accessibility") and caregiver-app ("07
Evening") screens from the same prototype aren't implemented here - they need
real features this codebase doesn't have yet (persisted accessibility
settings, a separate caregiver client), not just a visual pass.
"""

import base64
import os
from datetime import datetime

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

_SILHOUETTE_SVG = """<svg class="silhouette" viewBox="0 0 200 260" aria-hidden="true">
  <circle cx="100" cy="72" r="46"/>
  <path d="M22,258 C22,163 152,163 178,220 C186,236 188,248 188,258 Z"/>
</svg>"""


def _trend_display(trend_code):
    return _TREND_DISPLAY.get(trend_code, ("steady", "→"))


def _range_status(value):
    if value < 4.0:
        return "Low"
    if value > 10.0:
        return "High"
    return "In range"


def _now_time_str():
    now = datetime.now()
    hour = now.hour % 12 or 12
    return f"{hour}:{now.minute:02d}"


def _now_date_str():
    return datetime.now().strftime("%A · %d %B")


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

  /* Portrait mirror form factor: one narrow column, not a wide monitor. */
  .screen {
    position: relative;
    height: 100vh;
    max-width: 520px;
    margin: 0 auto;
    padding: 6vh 32px 6vh;
    display: flex;
    flex-direction: column;
  }

  .view { display: none; flex-direction: column; height: 100%; }
  .view.active { display: flex; }

  .header-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
  .time { font-weight: 800; font-size: clamp(36px, 9vw, 52px); letter-spacing: -1.5px; margin: 0; }
  .date { font-weight: 500; font-size: 16px; color: #8fa89a; margin: 6px 0 0; }

  .value-block { text-align: right; }
  .value-row { display: flex; align-items: baseline; gap: 8px; justify-content: flex-end; }
  .value { font-weight: 800; font-size: clamp(48px, 13vw, 68px); letter-spacing: -2px; margin: 0; line-height: 1; }
  .unit { font-weight: 500; font-size: 15px; color: #8fa89a; }

  .pill {
    display: inline-flex; align-items: center; gap: 8px; margin-top: 10px;
    background: #173326; border-radius: 100px; padding: 7px 14px 7px 12px;
  }
  .pill .dot { width: 9px; height: 9px; border-radius: 50%; background: #5bc08c; flex: none; }
  .pill span.label { font-weight: 600; font-size: 14px; color: #8fe3b4; white-space: nowrap; }
  .pill.warn .dot { background: #e0a458; }
  .pill.warn span.label { color: #f0c896; }
  .trend { display: block; font-weight: 500; font-size: 13.5px; color: #8fa89a; margin-top: 6px; }

  /* Masked ambient value (Pr1) - looks like a redacted bar, not a number. */
  .value-row.masked .value { opacity: 0.35; }

  .silhouette-wrap {
    flex: 1; display: flex; align-items: center; justify-content: center;
    position: relative; min-height: 0;
  }
  .silhouette { width: 46%; max-width: 190px; color: #d6e2d9; opacity: 0.09; }
  .silhouette circle, .silhouette path { fill: currentColor; }

  .asked-tag {
    display: inline-flex; align-items: center; gap: 6px; align-self: flex-end;
    font-weight: 600; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase;
    color: #8fe3b4; margin-top: 4px;
  }
  .question-bubble {
    position: absolute; top: 0; right: 0; max-width: 78%;
    background: #16291f; border-radius: 20px; padding: 14px 18px;
    font-weight: 500; font-size: 17px; line-height: 1.35; color: #edefea;
  }

  .bottom-block { padding-top: 4px; padding-bottom: 76px; }
  .quote {
    font-style: italic; font-size: clamp(19px, 5.5vw, 24px); line-height: 1.35; color: #d6e2d9;
    margin: 0 0 14px;
  }
  .mira-label {
    font-weight: 600; font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase;
    color: #5bc08c; margin: 0 0 6px;
  }
  #qa-answer { font-size: clamp(19px, 5vw, 24px); line-height: 1.4; color: #edefea; margin: 0 0 14px; }
  .disclaimer { font-size: 13px; color: #5c7167; margin: 0 0 14px; }

  .speaking { display: flex; align-items: center; gap: 10px; visibility: hidden; }
  .speaking.active { visibility: visible; }
  .speaking .bars { display: flex; align-items: flex-end; gap: 5px; height: 26px; }
  .speaking .bars span { display: block; width: 5px; border-radius: 3px; background: #5bc08c; }
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
  .speaking-label { font-weight: 500; font-size: 13px; color: #8fa89a; }

  /* --- connection view (06) --- */
  .conn-badge {
    display: inline-flex; align-items: center; gap: 8px; font-weight: 600; font-size: 13px;
    color: #f0c896; background: rgba(224,164,88,0.14); padding: 7px 14px; border-radius: 100px;
  }
  .conn-badge .dot { width: 9px; height: 9px; border-radius: 50%; background: #e0a458; }
  .conn-title { font-size: 22px; font-weight: 700; margin: 0 0 8px; }
  .conn-detail { font-size: 15.5px; color: #8fa89a; line-height: 1.4; margin: 0 0 18px; }
  .conn-last { font-size: 14.5px; color: #5c7167; }
  .conn-last strong { color: #edefea; }

  /* --- trend view (03) --- */
  .trend-stats { text-align: right; }
  .trend-stat { display: block; font-size: 14px; color: #8fa89a; margin-top: 4px; }
  .trend-stat strong { color: #edefea; font-weight: 700; }
  .chart-wrap { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; width: 100%; }
  .chart-bars { display: flex; align-items: flex-end; justify-content: center; gap: 1.5px; height: 68%; width: 100%; overflow: hidden; }
  .chart-bars .bar { flex: 1; max-width: 10px; min-width: 1.5px; border-radius: 3px 3px 1px 1px; background: #5bc08c; opacity: 0.9; }
  .chart-bars .bar.low, .chart-bars .bar.high { background: #e0a458; }

  /* --- alert view (04) --- */
  .screen.alert-mode { background: radial-gradient(ellipse at 50% 15%, #3a1610 0%, #200c0a 70%); }
  .alert-badge { display: inline-flex; align-items: center; gap: 8px; color: #ff9c8a; font-weight: 700; font-size: 15px; }
  .alert-value-row { display: flex; align-items: baseline; gap: 10px; justify-content: center; }
  .alert-value { font-weight: 800; font-size: clamp(64px, 20vw, 96px); letter-spacing: -3px; color: #ffe4de; margin: 0; }
  .alert-unit { font-size: 16px; color: #e2ab9f; }
  .alert-trend { display: block; text-align: center; font-size: 15px; color: #e2ab9f; margin-top: 6px; }
  .alert-message { font-size: clamp(20px, 5.5vw, 25px); font-weight: 600; line-height: 1.4; color: #ffe4de; margin: 0 0 14px; }
  .alert-hint { font-size: 14.5px; color: #e2ab9f; }

  /* --- mic control --- */
  #talk {
    position: absolute; bottom: 3vh; left: 50%; transform: translateX(-50%);
    width: 60px; height: 60px; border-radius: 50%; border: none;
    background: #173326; color: #8fe3b4; font-size: 22px; cursor: pointer;
  }
  #talk.recording { background: #c0483a; color: #edefea; }
</style>
</head>
<body>
  <div class="screen">

    <div id="ambientView" class="view {{ ambient_active }}">
      <div class="header-row">
        <div><p class="time">{{ time }}</p><p class="date">{{ date }}</p></div>
        <div class="value-block">
          <div class="value-row masked"><p class="value">&ndash;&ndash;</p><span class="unit">mmol/L</span></div>
          <div class="pill{{ pill_class }}"><span class="dot"></span><span class="label">{{ status }}</span></div>
          <span class="trend">{{ trend_label }} {{ trend_arrow }}</span>
        </div>
      </div>
      <div class="silhouette-wrap">{{ SILHOUETTE }}</div>
      <div class="bottom-block">
        <p class="quote">&ldquo;Ask about your glucose or a meal to hear more.&rdquo;</p>
      </div>
    </div>

    <div id="connectionView" class="view {{ connection_active }}">
      <div class="header-row">
        <div><p class="time">{{ time }}</p><p class="date">{{ date }}</p></div>
        <div class="conn-badge"><span class="dot"></span>Signal lost</div>
      </div>
      <div class="silhouette-wrap">{{ SILHOUETTE }}</div>
      <div class="bottom-block">
        <p class="conn-title">Sensor connection lost</p>
        <p class="conn-detail">Mira holds your last reading and its time until the sensor reconnects.</p>
        <p class="conn-last">Last reading <strong>{{ last_value }}</strong> &middot; {{ last_time }}</p>
      </div>
    </div>

    <div id="qaView" class="view">
      <div class="header-row">
        <p class="time" id="qa-time"></p>
        <span class="asked-tag">&#127908; You asked aloud</span>
      </div>
      <div class="silhouette-wrap">
        {{ SILHOUETTE }}
        <div class="question-bubble" id="qa-question"></div>
      </div>
      <div class="bottom-block">
        <div class="value-block" style="text-align:left; margin-bottom: 14px;">
          <div class="value-row"><p class="value" id="qa-value" style="font-size: 40px;"></p><span class="unit">mmol/L</span></div>
          <div class="pill" id="qa-pill"><span class="dot"></span><span class="label" id="qa-status-text"></span></div>
        </div>
        <p class="mira-label">Mira</p>
        <p id="qa-answer"></p>
        <p class="disclaimer">I share your numbers, not medical advice.</p>
        <div class="speaking" id="qaSpeaking">
          <div class="bars"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
          <span class="speaking-label">Speaking</span>
        </div>
      </div>
    </div>

    <div id="trendView" class="view">
      <div class="header-row">
        <div><p class="time" id="trend-time"></p><p class="date">Past 6 hours</p></div>
        <div class="trend-stats">
          <span class="trend-stat">Avg <strong id="trend-avg"></strong> mmol/L</span>
          <span class="trend-stat" id="trend-range-pct"></span>
        </div>
      </div>
      <div class="chart-wrap"><div class="chart-bars" id="chart-bars"></div></div>
      <div class="bottom-block">
        <p class="mira-label">Mira</p>
        <p id="trend-answer"></p>
        <div class="speaking" id="trendSpeaking">
          <div class="bars"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
          <span class="speaking-label">Speaking</span>
        </div>
      </div>
    </div>

    <div id="alertView" class="view">
      <div class="header-row">
        <p class="time" id="alert-time"></p>
        <span class="alert-badge">&#9888; <span id="alert-label"></span></span>
      </div>
      <div class="silhouette-wrap">
        <div>
          <div class="alert-value-row"><p class="alert-value" id="alert-value"></p><span class="alert-unit">mmol/L</span></div>
          <span class="alert-trend" id="alert-trend"></span>
        </div>
      </div>
      <div class="bottom-block">
        <p class="alert-message" id="alert-message"></p>
        <p class="alert-hint">Say &ldquo;I've had it&rdquo; to confirm.</p>
      </div>
    </div>

    <button id="talk" title="Hold to ask">&#127908;</button>
    <audio id="player" hidden></audio>
  </div>

<script>
const screenEl = document.querySelector(".screen");
const talkButton = document.getElementById("talk");
const idleView = document.getElementById({{ idle_view_js }});
const qaView = document.getElementById("qaView");
const trendView = document.getElementById("trendView");
const alertView = document.getElementById("alertView");
const qaSpeaking = document.getElementById("qaSpeaking");
const trendSpeaking = document.getElementById("trendSpeaking");
const qaPill = document.getElementById("qa-pill");
const player = document.getElementById("player");
const PLAYBACK_RATE = 1.25;
const RETURN_TO_IDLE_MS = 10000;
const RETURN_TO_IDLE_ALERT_MS = 25000;

let recorder, chunks, returnTimer, activeSpeakingEl;

function renderTrendChart(readings) {
  const bars = document.getElementById("chart-bars");
  bars.innerHTML = "";
  const values = readings.map((r) => r.value);
  const min = Math.min(...values), max = Math.max(...values);
  const span = (max - min) || 1;
  readings.forEach((r) => {
    const bar = document.createElement("div");
    bar.className = "bar" + (r.value < 4 ? " low" : r.value > 10 ? " high" : "");
    bar.style.height = (15 + ((r.value - min) / span) * 85) + "%";
    bars.appendChild(bar);
  });
}

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

function hideAllViews() {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
}

async function sendRecording() {
  const blob = new Blob(chunks, { type: "audio/webm" });
  const formData = new FormData();
  formData.append("audio", blob, "audio.webm");

  const resp = await fetch("/ask", { method: "POST", body: formData });
  const data = await resp.json();

  clearTimeout(returnTimer);
  hideAllViews();

  if (data.message_type === "urgent") {
    document.getElementById("alert-time").textContent = data.time;
    document.getElementById("alert-label").textContent = data.glucose_status;
    document.getElementById("alert-value").textContent = data.glucose_value;
    document.getElementById("alert-trend").textContent = data.trend_label + " " + data.trend_arrow;
    document.getElementById("alert-message").textContent = data.response_text;
    alertView.classList.add("active");
    screenEl.classList.add("alert-mode");
    activeSpeakingEl = null;
  } else if (data.message_type === "trend") {
    document.getElementById("trend-time").textContent = data.time;
    document.getElementById("trend-avg").textContent = data.trend.average;
    document.getElementById("trend-range-pct").textContent = data.trend.time_in_range_pct + "% in range";
    document.getElementById("trend-answer").textContent = data.response_text;
    renderTrendChart(data.trend.readings);
    trendView.classList.add("active");
    activeSpeakingEl = trendSpeaking;
  } else {
    document.getElementById("qa-time").textContent = data.time;
    document.getElementById("qa-question").textContent = "“" + data.question_text + "”";
    document.getElementById("qa-answer").textContent = data.response_text;
    if (data.glucose_value !== null) {
      document.getElementById("qa-value").textContent = data.glucose_value;
      document.getElementById("qa-status-text").textContent = data.glucose_status;
    } else {
      document.getElementById("qa-value").textContent = "–";
      document.getElementById("qa-status-text").textContent = data.glucose_status;
    }
    qaPill.classList.toggle("warn", data.glucose_value === null);
    qaView.classList.add("active");
    activeSpeakingEl = qaSpeaking;
  }

  const delay = data.message_type === "urgent" ? RETURN_TO_IDLE_ALERT_MS : RETURN_TO_IDLE_MS;

  if (data.audio_base64) {
    player.src = "data:audio/wav;base64," + data.audio_base64;
    player.playbackRate = PLAYBACK_RATE;
    if (activeSpeakingEl) activeSpeakingEl.classList.add("active");
    player.onended = () => {
      if (activeSpeakingEl) activeSpeakingEl.classList.remove("active");
      returnTimer = setTimeout(returnToIdle, delay);
    };
    player.play();
  } else {
    returnTimer = setTimeout(returnToIdle, delay);
  }
}

function returnToIdle() {
  hideAllViews();
  screenEl.classList.remove("alert-mode");
  idleView.classList.add("active");
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
    status = _orchestrator.glucose_store.status()
    time_str, date_str = _now_time_str(), _now_date_str()

    if status["available"]:
        reading = status["reading"]
        trend_label, trend_arrow = _trend_display(reading.get("trend"))
        page = (
            _PAGE.replace("{{ ambient_active }}", "active")
            .replace("{{ connection_active }}", "")
            .replace("{{ status }}", _range_status(reading["value"]))
            .replace("{{ pill_class }}", "")
            .replace("{{ trend_label }}", trend_label)
            .replace("{{ trend_arrow }}", trend_arrow)
            .replace("{{ last_value }}", "")
            .replace("{{ last_time }}", "")
            .replace("{{ idle_view_js }}", '"ambientView"')
        )
    else:
        last = status["reading"]
        last_value = f"{last['value']} mmol/L" if last else "unknown"
        page = (
            _PAGE.replace("{{ ambient_active }}", "")
            .replace("{{ connection_active }}", "active")
            .replace("{{ status }}", "")
            .replace("{{ pill_class }}", "")
            .replace("{{ trend_label }}", "")
            .replace("{{ trend_arrow }}", "")
            .replace("{{ last_value }}", last_value)
            .replace("{{ last_time }}", last.get("displayTime", "") if last else "")
            .replace("{{ idle_view_js }}", '"connectionView"')
        )

    return (
        page.replace("{{ time }}", time_str)
        .replace("{{ date }}", date_str)
        .replace("{{ SILHOUETTE }}", _SILHOUETTE_SVG)
    )


@app.route("/ask", methods=["POST"])
def ask():
    audio_file = request.files["audio"]
    question_text = voice.transcribe(audio_file.read(), audio_file.filename)
    result = _orchestrator.handle_query(question_text)

    try:
        audio_b64 = base64.b64encode(voice.synthesize(result["response_text"])).decode("ascii")
    except Exception:
        audio_b64 = None

    reading = result["glucose_reading"]
    if reading is not None:
        glucose_value = reading["value"]
        glucose_status = _range_status(glucose_value)
        trend_label, trend_arrow = _trend_display(reading.get("trend"))
    else:
        glucose_value = None
        glucose_status = "Data unavailable"
        trend_label, trend_arrow = "", ""

    payload = {
        "question_text": question_text,
        "response_text": result["response_text"],
        "message_type": result["message_type"],
        "glucose_value": glucose_value,
        "glucose_status": glucose_status,
        "trend_label": trend_label,
        "trend_arrow": trend_arrow,
        "time": _now_time_str(),
        "audio_base64": audio_b64,
    }

    if result["message_type"] == "trend":
        stats = result["trend_stats"]
        payload["trend"] = {
            "average": stats.average,
            "minimum": stats.minimum,
            "maximum": stats.maximum,
            "direction": stats.direction,
            "time_in_range_pct": stats.time_in_range_pct,
            "readings": [{"value": r["value"]} for r in stats.readings],
        }

    return jsonify(payload)


def run():
    port = int(os.environ.get("MIRA_DISPLAY_PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
