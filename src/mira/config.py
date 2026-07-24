"""Minimal .env loader (no third-party dependency).

Reads KEY=VALUE lines from a .env file at the project root and injects them
into os.environ. Existing environment variables are never overwritten, so
real environment settings always win over the file.
"""

import os
from pathlib import Path

# config.py lives at src/mira/config.py; project root is three levels up.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_loaded = False


def load_env(path=None, override=False):
    """Load a .env file into os.environ. Safe to call multiple times."""
    global _loaded
    if _loaded and path is None:
        return
    env_path = Path(path) if path else _PROJECT_ROOT / ".env"
    if not env_path.exists():
        _loaded = True
        return

    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value

    if path is None:
        _loaded = True
