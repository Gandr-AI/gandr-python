"""The client. Thin by design: the API does the work, this file just speaks HTTP."""

from __future__ import annotations

import json
import urllib.request
import urllib.error

DOORS = (
    "https://tts.gandr.ai",      # West (primary)
    "https://tts-nyc.gandr.ai",  # NYC
    "https://tts-eu.gandr.ai",   # EU
)

VOICES = ("gandr-ava", "gandr-dane", "gandr-jenny",
          "gandr-leo", "gandr-lewis", "gandr-mia")

Voice = str  # a voice id, e.g. "gandr-ava"


class GandrError(Exception):
    """Raised on any non-200 from the door. Carries the door's own message."""

    def __init__(self, status: int, payload: dict | str):
        self.status = status
        self.payload = payload
        msg = payload.get("error", payload) if isinstance(payload, dict) else payload
        hint = payload.get("hint", "") if isinstance(payload, dict) else ""
        super().__init__(f"[{status}] {msg}" + (f", {hint}" if hint else ""))


class Gandr:
    """One instance per API key. Doors fail over automatically."""

    def __init__(self, api_key: str, *, timeout: float = 60.0):
        if not api_key:
            raise ValueError("api_key is required, get one at https://gandr.ai")
        self.api_key = api_key
        self.timeout = timeout

    def say(
        self,
        text: str,
        *,
        voice: Voice = "gandr-ava",
        language: str = "en",
        sample_rate: int = 24000,
        temperature: float | None = None,
        cfg_weight: float | None = None,
        speed: float | None = None,
        volume: float | None = None,
        pronunciation: list[dict] | None = None,
    ) -> bytes:
        """Render text to a WAV file (returned as bytes).

        temperature: 0.1 to 1.2, pitch range / melody. Omit for the tuned default.
        cfg_weight:  0.2 to 1.0, pacing (lower = more spacious).
        speed:       0.6 to 1.5 pace multiplier.  volume: 0.5 to 2.0 gain.
        sample_rate: 8000 to 48000, resampled server-side.
        pronunciation: [{"text": "Nguyen", "pronunciation": "win"}], sounds-like.
        """
        if not text or not text.strip():
            raise ValueError("text must not be empty")
        if len(text) > 2000:
            raise ValueError("text is over the 2000-character request cap, split it")
        body: dict = {
            "transcript": text,
            "language": language,
            "voice": {"mode": "id", "id": voice},
            "output_format": {"sample_rate": sample_rate},
        }
        if temperature is not None:
            body["temperature"] = temperature
        if cfg_weight is not None:
            body["cfg_weight"] = cfg_weight
        if speed is not None:
            body["speed"] = speed
        if volume is not None:
            body["volume"] = volume
        if pronunciation:
            body["pronunciation_dict"] = pronunciation
        return self._post("/v1/tts/bytes", body)

    def voices(self) -> list[dict]:
        """List the voice catalog (never wakes the fleet)."""
        return json.loads(self._request("GET", "/v1/voices", None))

    def usage(self) -> dict:
        """Characters used vs quota for this key. May wake a cold fleet."""
        return json.loads(self._request("GET", "/v1/usage", None))

    # ── plumbing ──────────────────────────────────────────────────────

    def _post(self, path: str, body: dict) -> bytes:
        return self._request("POST", path, json.dumps(body).encode())

    def _request(self, method: str, path: str, payload: bytes | None) -> bytes:
        last: Exception | None = None
        for door in DOORS:
            req = urllib.request.Request(
                door + path, data=payload, method=method,
                headers={"x-api-key": self.api_key,
                         "content-type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                # 4xx is the door answering, do not fail over on a real answer
                try:
                    raise GandrError(e.code, json.loads(e.read()))
                except json.JSONDecodeError:
                    raise GandrError(e.code, e.reason)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e  # door unreachable, try the next region
        raise GandrError(0, f"all doors unreachable: {last}")
