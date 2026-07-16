"""Speech-in (Phase 2b): microphone -> text, fully local.

Records from the mic (silence-auto-stop) and transcribes with faster-whisper —
offline, no API key, nothing leaves the machine, and independent of Voicebox
(the output side). The only thing this produces is the string that would
otherwise have been typed; it is handed straight to classify(). Nothing
downstream (shape, fact packet, narrator, voice) changes.

If the mic is unavailable, permission is denied, or nothing is said, this returns
None and the caller reports it plainly — same "no dead air / no raw error" spirit.
"""

from __future__ import annotations

import os
import sys
import warnings
from typing import Optional

import numpy as np

SAMPLE_RATE = 16000
_MODEL_NAME = os.environ.get("BROCA_WHISPER_MODEL", "base.en")
# RMS energy (float32) above which a 100ms block counts as speech. Env-tunable.
_THRESHOLD = float(os.environ.get("BROCA_MIC_THRESHOLD", "0.015"))

# Biases Whisper's decoder toward CORTEX/AXON vocabulary it was never trained on,
# so "AXON" stops being transcribed as "action" and ticket codes keep the UX-###
# form. Passed as `initial_prompt` (a decoder prior) — it is NOT added to the
# transcript. Env-overridable via BROCA_STT_PROMPT.
_DOMAIN_PROMPT = os.environ.get(
    "BROCA_STT_PROMPT",
    "This is a conversation about CORTEX, a personal agent system whose components "
    "are THALAMUS, HIPPOCAMPUS, BROCA, and PREFRONTAL. It tracks the AXON design "
    "system in Jira tickets like UX-344, UX-350, and UX-353.",
)

_model = None  # lazy, cached across calls


def _log(msg: str) -> None:
    print(f"[listen] {msg}", file=sys.stderr)


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(_MODEL_NAME, device="cpu", compute_type="int8")
    return _model


def record(max_seconds: float = 15.0, silence_trail: float = 1.2,
           start_timeout: float = 6.0) -> Optional[np.ndarray]:
    """Capture one utterance. Waits up to start_timeout for speech to begin,
    then records until silence_trail seconds of quiet (or max_seconds). Returns
    a float32 mono array at 16 kHz, or None if nothing was captured."""
    try:
        import sounddevice as sd
    except Exception as e:  # noqa: BLE001
        _log(f"audio input unavailable ({type(e).__name__})")
        return None

    block = 0.1
    n = int(SAMPLE_RATE * block)
    frames: list[np.ndarray] = []
    speaking = False
    silence = 0.0
    waited = 0.0
    elapsed = 0.0
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            blocksize=n) as stream:
            while elapsed < max_seconds:
                data, _ = stream.read(n)
                chunk = data[:, 0]
                rms = float(np.sqrt(np.mean(chunk * chunk)))
                elapsed += block
                if not speaking:
                    waited += block
                    if rms >= _THRESHOLD:
                        speaking = True
                        frames.append(chunk)
                    elif waited >= start_timeout:
                        return None  # nothing said
                else:
                    frames.append(chunk)
                    if rms < _THRESHOLD:
                        silence += block
                        if silence >= silence_trail:
                            break
                    else:
                        silence = 0.0
    except Exception as e:  # noqa: BLE001 — mic open/permission/read failure
        _log(f"mic capture failed ({type(e).__name__}: {e})")
        return None

    if not frames:
        return None
    return np.concatenate(frames).astype(np.float32)


def transcribe(audio: np.ndarray) -> str:
    model = _get_model()
    # The mel matmul emits benign divide/overflow warnings under numpy 2.x; mute.
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        segments, _ = model.transcribe(audio, language="en", initial_prompt=_DOMAIN_PROMPT)
        return "".join(s.text for s in segments).strip()


def listen() -> Optional[str]:
    """Record one spoken utterance and return its transcription (or None)."""
    audio = record()
    if audio is None:
        return None
    text = transcribe(audio)
    return text or None
