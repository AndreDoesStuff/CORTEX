"""The shaped-answer type and single-session context.

A ShapedAnswer always lands in exactly one confidence shape. `headline` is the
brief spoken lead; `detail` is the full on-screen text (with citations) shown on
"tell me more"; `spoken` overrides what `say` voices (used when expanding).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# The six answer shapes BROCA is allowed to emit — never blended in one breath.
# "conversational" is the only shape where personality is safe, because it makes
# no factual claim about anything HIPPOCAMPUS holds.
SHAPES = {"grounded", "inferred", "unknown", "partial", "scope", "conversational"}


@dataclass
class ShapedAnswer:
    shape: str
    headline: str                     # brief lead — printed and spoken (deterministic fallback)
    detail: str = ""                  # full text w/ citations — shown on expand
    spoken: str = ""                  # what say() voices; falls back to headline
    records: list[Any] = field(default_factory=list)  # provenance (MemoryRecord)
    values: dict[str, Any] = field(default_factory=dict)  # fact packet for the narrator

    def voice_text(self) -> str:
        return self.spoken or self.headline


@dataclass
class Session:
    """Within-session context only. Never persisted, never carried across runs."""

    last: ShapedAnswer | None = None
