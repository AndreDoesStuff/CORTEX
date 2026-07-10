"""Voice-out via macOS `say`. First-pass TTS, no external API.

If a more natural voice is wanted later, swap this for a TTS API — the rest of
BROCA doesn't change. On non-macOS (no `say`), this no-ops; the text is always
printed regardless, so nothing is lost.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional

_SAY = shutil.which("say")


def available() -> bool:
    return _SAY is not None


def speak(text: str, enabled: bool = True, out_file: Optional[str] = None) -> None:
    if not text:
        return
    if out_file:  # write audio to a file instead of playing (used for testing)
        subprocess.run([_SAY or "say", "-o", out_file, text], check=False)
        return
    if not enabled or _SAY is None:
        return
    subprocess.run([_SAY, text], check=False)
