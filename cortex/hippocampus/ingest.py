"""Turn THALAMUS normalized signals into immutable memory records.

Input is THALAMUS's Deliverable-2 shape (source_id, fetched_at, category, raw,
summary) — either from a saved snapshot (list of dicts) or a live pull.
"""

from __future__ import annotations

from typing import Any, Optional

from ..registry import SourceConfig, load_sources
from . import extract
from .batch import BatchCandidate, assign_batches
from .record import MemoryRecord, memory_id, parse_dt


def signals_to_records(
    signals: list[dict[str, Any]], sources: list[SourceConfig]
) -> list[MemoryRecord]:
    type_by_id = {s.id: s.type for s in sources}
    records: list[MemoryRecord] = []
    candidates: list[BatchCandidate] = []

    for sig in signals:
        sid = sig["source_id"]
        stype = type_by_id.get(sid, "unknown")
        raw = sig["raw"]
        fetched = sig["fetched_at"]

        occ = extract.occurred_at(stype, raw, fetched)
        life = extract.lifecycle_state(stype, raw)
        mid = memory_id(sid, extract.entity_key(stype, raw), occ)

        records.append(
            MemoryRecord(
                memory_id=mid,
                source_id=sid,
                occurred_at=occ,
                fetched_at=fetched,
                signal_category=sig["category"],
                lifecycle_state=life,
                batch_id=None,
                raw=raw,
                summary=sig["summary"],
            )
        )
        candidates.append(
            BatchCandidate(
                memory_id=mid,
                source_id=sid,
                actor=extract.actor(stype, raw),
                signature=extract.batch_signature(stype, raw, life),
                occurred_dt=parse_dt(occ),
                lifecycle_state=life,
            )
        )

    batch_ids = assign_batches(candidates)
    for r in records:
        r.batch_id = batch_ids.get(r.memory_id)
    return records


def collect_live(
    sources: list[SourceConfig], since, only: Optional[str] = None
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Run THALAMUS adapters and return signal dicts + skipped/errored notes."""
    import httpx

    from ..adapters import ADAPTERS, SourceSkipped
    from ..secrets import MissingSecret

    signals: list[dict[str, Any]] = []
    skipped: list[str] = []
    errored: list[str] = []
    with httpx.Client(timeout=30.0) as client:
        for src in sources:
            if only and src.id != only:
                continue
            if not src.enabled:
                skipped.append(f"{src.id} (disabled)")
                continue
            adapter_cls = ADAPTERS.get(src.type)
            if adapter_cls is None:
                errored.append(f"{src.id} (no adapter for {src.type!r})")
                continue
            try:
                signals.extend(s.to_dict() for s in adapter_cls(src).fetch(since, client))
            except (SourceSkipped, MissingSecret) as e:
                skipped.append(f"{src.id} ({e})")
            except httpx.HTTPError as e:
                errored.append(f"{src.id} ({e})")
    return signals, skipped, errored


def load_registry(config_path: str = "sources.json") -> list[SourceConfig]:
    return load_sources(config_path)
