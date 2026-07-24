"""Dexcom API client.

Handles OAuth 2.0 token refresh and fetching estimated glucose values (EGVs)
from the Dexcom sandbox (or production) API.

Dexcom returns glucose in mg/dL; this client converts to mmol/L to match the
project convention (see sandbox_egvs.json).
"""

import os
from datetime import datetime, timedelta

import requests

# Dexcom reports mg/dL; divide by this to get mmol/L.
_MGDL_PER_MMOL = 18.0
# Access tokens are short-lived; refresh a little early to avoid races.
_TOKEN_SKEW = timedelta(seconds=60)


class DexcomConfigError(RuntimeError):
    """Raised when required Dexcom credentials are missing."""


class DexcomClient:
    def __init__(
        self,
        client_id=None,
        client_secret=None,
        refresh_token=None,
        base_url=None,
    ):
        self.base_url = (base_url or os.environ.get("DEXCOM_BASE_URL")
                         or "https://sandbox-api.dexcom.com").rstrip("/")
        self.client_id = client_id or os.environ.get("DEXCOM_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("DEXCOM_CLIENT_SECRET")
        self.refresh_token = refresh_token or os.environ.get("DEXCOM_REFRESH_TOKEN")

        missing = [
            name for name, val in (
                ("DEXCOM_CLIENT_ID", self.client_id),
                ("DEXCOM_CLIENT_SECRET", self.client_secret),
                ("DEXCOM_REFRESH_TOKEN", self.refresh_token),
            )
            if not val
        ]
        if missing:
            raise DexcomConfigError(
                "Missing Dexcom credentials: " + ", ".join(missing)
                + ". Run `python -m mira.data.dexcom_auth` to obtain a refresh token."
            )

        self._access_token = None
        self._access_expires_at = datetime.min

    @classmethod
    def from_env(cls):
        """Build a client from environment variables, or return None if unconfigured."""
        from mira.config import load_env
        load_env()
        try:
            return cls()
        except DexcomConfigError:
            return None

    def _ensure_token(self):
        if self._access_token and datetime.utcnow() < self._access_expires_at - _TOKEN_SKEW:
            return
        resp = requests.post(
            f"{self.base_url}/v2/oauth2/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._access_token = payload["access_token"]
        # Dexcom rotates the refresh token on each use; keep the newest one.
        if payload.get("refresh_token"):
            self.refresh_token = payload["refresh_token"]
        self._access_expires_at = datetime.utcnow() + timedelta(
            seconds=int(payload.get("expires_in", 7200))
        )

    def get_egvs(self, start=None, end=None):
        """Fetch EGVs in a time window, normalized to the GlucoseStore shape.

        Returns a list of dicts: {"displayTime", "value" (mmol/L), "trend"},
        oldest first.
        """
        end = end or datetime.utcnow()
        start = start or (end - timedelta(hours=24))

        self._ensure_token()
        resp = requests.get(
            f"{self.base_url}/v3/users/self/egvs",
            headers={"Authorization": f"Bearer {self._access_token}"},
            params={
                "startDate": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "endDate": end.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            timeout=15,
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        readings = [self._normalize(r) for r in records]
        readings = [r for r in readings if r is not None]
        readings.sort(key=lambda r: r["displayTime"])
        return readings

    @staticmethod
    def _normalize(record):
        value = record.get("value")
        if value is None:
            return None  # gaps / calibration records have no value
        return {
            "displayTime": record.get("displayTime"),
            "value": round(value / _MGDL_PER_MMOL, 1),
            "trend": record.get("trend"),
        }
