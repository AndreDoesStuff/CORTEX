"""The one normalized signal shape every adapter must emit (Deliverable 2).

Deliberately dumb: no ranking, no scoring, no inference beyond what's literally
in `raw`. `raw` is mandatory on every record — it is the provenance anchor that
Phase 1 (HIPPOCAMPUS) will build on. Never drop it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# Best-effort tag. Does not need to be smart yet (Phase 0). Not a priority score.
Category = Literal["job", "idea", "trend", "fyi"]


@dataclass
class Signal:
    source_id: str
    fetched_at: str  # ISO8601, UTC
    category: Category
    raw: dict[str, Any] = field(repr=False)  # untouched original payload — provenance
    summary: str  # one line, factual, no inference beyond what's in `raw`

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "fetched_at": self.fetched_at,
            "category": self.category,
            "raw": self.raw,
            "summary": self.summary,
        }
