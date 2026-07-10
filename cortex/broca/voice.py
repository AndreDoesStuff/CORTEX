"""Voice-out: Voicebox (local, on-device voice cloning) primary; macOS `say` fallback.

Voicebox runs a local server (no API key, no cost, nothing leaves the machine) and
speaks in André's cloned voice. To guarantee "never dead air" (the standing narrator
principle), this OWNS playback rather than trusting fire-and-forget:

    resolve profile -> POST /generate (silent synthesis) -> bounded poll for
    completion -> GET /audio -> afplay

On ANY failure — app not running, profile not found, synthesis failed, synthesis
not finished within VOICEBOX_TIMEOUT, audio unfetchable — it falls back to
`say -v Samantha` immediately. One generation attempt (the poll waits on that one
job; it is not a retry loop). Failure reason is logged quietly to stderr, never spoken.

Purely the last step: receives already-validated text from the narrator layer.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Optional

import httpx

_SAY = shutil.which("say")
_AFPLAY = shutil.which("afplay")
FALLBACK_VOICE = "Samantha"

VOICEBOX_URL = os.environ.get("VOICEBOX_URL", "http://127.0.0.1:17493")
# Wait at most this long for one synthesis before falling back (latency accepted
# to avoid silence). Configurable for tuning/testing.
VOICEBOX_TIMEOUT = float(os.environ.get("VOICEBOX_TIMEOUT", "25"))
_HTTP = httpx.Timeout(10.0, connect=2.0)   # fail fast on connect (app closed)
_POLL_INTERVAL = 0.4
_DONE = "completed"
_FAILED = {"failed", "error", "cancelled", "canceled"}


def _log(msg: str) -> None:
    print(f"[voice] {msg}", file=sys.stderr)


def available() -> bool:
    return _SAY is not None or bool(os.environ.get("VOICEBOX_PROFILE_NAME"))


def _resolve_profile_id(client: httpx.Client, name: str) -> Optional[str]:
    r = client.get(f"{VOICEBOX_URL}/profiles", timeout=_HTTP)
    r.raise_for_status()
    for p in r.json():
        if p.get("name") == name:  # exact match (byte-for-byte; NFC on both sides)
            return p.get("id")
    return None


def _voicebox_render(text: str, profile: str) -> Optional[bytes]:
    """One generation attempt. Returns audio bytes on success, else None (logged)."""
    try:
        with httpx.Client() as client:
            pid = _resolve_profile_id(client, profile)
            if not pid:
                _log(f"Voicebox profile {profile!r} not found — using {FALLBACK_VOICE}")
                return None
            r = client.post(f"{VOICEBOX_URL}/generate",
                            json={"profile_id": pid, "text": text}, timeout=_HTTP)
            if r.status_code != 200:
                _log(f"Voicebox generate HTTP {r.status_code} — using {FALLBACK_VOICE}")
                return None
            gid = r.json().get("id")
            if not gid:
                _log(f"Voicebox returned no generation id — using {FALLBACK_VOICE}")
                return None

            deadline = time.monotonic() + VOICEBOX_TIMEOUT
            status = None
            while time.monotonic() < deadline:
                s = client.get(f"{VOICEBOX_URL}/history/{gid}", timeout=_HTTP)
                if s.status_code == 200:
                    status = s.json().get("status")
                    if status == _DONE:
                        break
                    if status in _FAILED:
                        _log(f"Voicebox synthesis {status} — using {FALLBACK_VOICE}")
                        return None
                time.sleep(_POLL_INTERVAL)
            if status != _DONE:
                _log(f"Voicebox synthesis unfinished after {VOICEBOX_TIMEOUT:.0f}s "
                     f"— using {FALLBACK_VOICE}")
                return None

            a = client.get(f"{VOICEBOX_URL}/audio/{gid}", timeout=_HTTP)
            if a.status_code != 200 or not a.content:
                _log(f"Voicebox audio fetch HTTP {a.status_code} — using {FALLBACK_VOICE}")
                return None
            return a.content
    except httpx.HTTPError as e:
        _log(f"Voicebox not responding ({type(e).__name__}) — using {FALLBACK_VOICE}")
        return None


def _play_wav(audio: bytes) -> bool:
    if _AFPLAY is None:
        _log(f"afplay unavailable — using {FALLBACK_VOICE}")
        return False
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio)
            path = f.name
        subprocess.run([_AFPLAY, path], check=False)
        return True
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def _say(text: str, out_file: Optional[str] = None) -> None:
    if _SAY is None:
        return
    args = [_SAY, "-v", FALLBACK_VOICE]
    if out_file:
        args += ["-o", out_file]
    subprocess.run(args + [text], check=False)


def speak(text: str, enabled: bool = True, out_file: Optional[str] = None) -> None:
    if not text:
        return
    if out_file:  # deterministic capture path — always the local say voice
        _say(text, out_file)
        return
    if not enabled:
        return
    profile = os.environ.get("VOICEBOX_PROFILE_NAME")
    if profile:
        audio = _voicebox_render(text, profile)
        if audio is not None and _play_wav(audio):
            return  # André's cloned voice played
    _say(text)  # fallback — unconfigured, or the one attempt failed/timed out
