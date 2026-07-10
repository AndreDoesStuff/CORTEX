"""The immutable memory record + stable id + robust timestamp parsing."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


def parse_dt(s: str) -> datetime:
    """Parse the varied ISO8601 shapes THALAMUS raw payloads carry.

    Handles Jira's colon-less offsets ("+0200"), trailing "Z", and fractional
    seconds — none of which Python 3.9's bare fromisoformat accepts.
    """
    s = s.strip().replace("Z", "+00:00")
    m = re.search(r"([+-]\d{2})(\d{2})$", s)  # +0200 -> +02:00
    if m:
        s = s[: m.start()] + m.group(1) + ":" + m.group(2)
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def memory_id(source_id: str, entity_key: str, occurred_at: str) -> str:
    """Stable hash of source + the event's own id + its own timestamp.

    Including occurred_at is deliberate: when a ticket's state changes, its new
    `updated` timestamp yields a NEW memory_id, so the change is appended as a
    fresh fact while the prior state remains in the log as history.
    """
    h = hashlib.sha256(f"{source_id}|{entity_key}|{occurred_at}".encode()).hexdigest()
    return h[:16]


@dataclass
class MemoryRecord:
    memory_id: str
    source_id: str
    occurred_at: str          # the event's OWN timestamp from raw, not fetch time
    fetched_at: str           # when THALAMUS pulled it
    signal_category: str      # job | idea | trend | fyi (from THALAMUS)
    lifecycle_state: str      # open | closed | obsolete | n/a (explicit raw field)
    batch_id: Optional[str]   # shared by records that are one real-world batch event
    raw: dict[str, Any]       # mandatory, untouched — provenance anchor
    summary: str              # naive, factual

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "source_id": self.source_id,
            "occurred_at": self.occurred_at,
            "fetched_at": self.fetched_at,
            "signal_category": self.signal_category,
            "lifecycle_state": self.lifecycle_state,
            "batch_id": self.batch_id,
            "raw": self.raw,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MemoryRecord":
        return cls(
            memory_id=d["memory_id"],
            source_id=d["source_id"],
            occurred_at=d["occurred_at"],
            fetched_at=d["fetched_at"],
            signal_category=d["signal_category"],
            lifecycle_state=d["lifecycle_state"],
            batch_id=d.get("batch_id"),
            raw=d["raw"],
            summary=d["summary"],
        )
