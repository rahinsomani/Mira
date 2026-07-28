"""Audit log for safety-related and scripted messages (D4).

Every scripted/safety message Mira speaks instead of a normal LLM answer -
urgent alerts, safety-check blocks, LLM-outage fallbacks, and CGM-unavailable
notices - gets one line here with a timestamp, so they can be reviewed later.
"""

import json
from datetime import datetime
from pathlib import Path

# audit_log.py lives at src/mira/audit_log.py; project root is two levels up.
_LOG_FILE = Path(__file__).resolve().parents[2] / "audit.log"


def log(event_type, message, **extra):
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "message": message,
        **extra,
    }
    with open(_LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
