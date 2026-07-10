"""Grounded, cited queries over the memory log.

Domain is joined from the source registry at query time (not stored per record).
Every returned line carries a citation back to a specific memory + its source.
No ranking, no prioritization — that's PREFRONTAL (Phase 3).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..registry import SourceConfig
from . import extract
from .record import MemoryRecord, parse_dt
from .store import MemoryStore


class Memory:
    def __init__(self, store: MemoryStore, sources: list[SourceConfig]):
        self.records = store.all()
        self._domain = {s.id: s.domain for s in sources}
        self._type = {s.id: s.type for s in sources}

    def domain_of(self, source_id: str) -> str:
        return self._domain.get(source_id, "unknown")

    # --- queries ---------------------------------------------------------
    def open_work(self, domain: str) -> list[MemoryRecord]:
        """Exit test 2: live work in a domain, by lifecycle_state alone."""
        return [
            r
            for r in self.records
            if self.domain_of(r.source_id) == domain and r.lifecycle_state == "open"
        ]

    def recent(
        self,
        source_id: Optional[str] = None,
        domain: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[MemoryRecord]:
        out = []
        for r in self.records:
            if source_id and r.source_id != source_id:
                continue
            if domain and self.domain_of(r.source_id) != domain:
                continue
            if since and parse_dt(r.occurred_at) < since:
                continue
            out.append(r)
        return sorted(out, key=lambda r: r.occurred_at, reverse=True)

    # --- citation rendering ---------------------------------------------
    def cite(self, r: MemoryRecord) -> str:
        ref = extract.entity_ref(self._type.get(r.source_id, "unknown"), r.raw)
        return (
            f"↳ cited: memory_id={r.memory_id} · source={r.source_id} "
            f"· domain={self.domain_of(r.source_id)} · occurred_at={r.occurred_at} · {ref}"
        )

    def render(self, records: list[MemoryRecord], collapse_batches: bool = True) -> str:
        """Render results as grounded lines, collapsing batch events into one
        line (with the member count + citations) instead of N near-identical rows."""
        lines: list[str] = []
        seen_batches: set[str] = set()
        singles = [r for r in records if not r.batch_id]
        batched: dict[str, list[MemoryRecord]] = {}
        for r in records:
            if r.batch_id:
                batched.setdefault(r.batch_id, []).append(r)

        ordered = sorted(records, key=lambda r: r.occurred_at, reverse=True)
        for r in ordered:
            if collapse_batches and r.batch_id:
                if r.batch_id in seen_batches:
                    continue
                seen_batches.add(r.batch_id)
                members = batched[r.batch_id]
                keys = ", ".join(
                    extract.entity_ref(self._type.get(m.source_id, "unknown"), m.raw)
                    for m in members[:5]
                )
                more = "" if len(members) <= 5 else f", +{len(members) - 5} more"
                lines.append(
                    f"· [BATCH {r.batch_id}] {len(members)} records — one bulk event "
                    f"[{r.signal_category}/{r.lifecycle_state}] around {r.occurred_at}"
                )
                lines.append(f"    members: {keys}{more}")
            else:
                lines.append(
                    f"· [{r.signal_category}/{r.lifecycle_state}] {r.summary}"
                )
                lines.append(f"    {self.cite(r)}")
        return "\n".join(lines) if lines else "(no grounded records)"
