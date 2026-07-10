"""Append-only, immutable memory log (JSONL, one record per line).

The store only ever appends. There is no update and no delete method — that is
the Phase 1 core principle enforced in code, not just convention. Re-ingesting
the same THALAMUS pull is idempotent: records already present (by memory_id) are
skipped, never rewritten.
"""

from __future__ import annotations

import json
from pathlib import Path

from .record import MemoryRecord


class MemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._seen: set[str] = set()
        if self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self._seen.add(json.loads(line)["memory_id"])

    def append(self, records: list[MemoryRecord]) -> int:
        """Append new records; skip any whose memory_id already exists. Returns
        the number actually written."""
        added = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            for r in records:
                if r.memory_id in self._seen:
                    continue
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
                self._seen.add(r.memory_id)
                added += 1
        return added

    def all(self) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as f:
            return [MemoryRecord.from_dict(json.loads(line)) for line in f if line.strip()]

    def __len__(self) -> int:
        return len(self._seen)
