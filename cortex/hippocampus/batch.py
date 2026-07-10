"""Batch clustering: collapse one real-world batch event (e.g. a bulk close of
39 tickets) into a shared batch_id — WITHOUT dropping any record.

This is structural dedup of what's already explicit in the data, not inference
and not summarization. Every record keeps its own raw and its own memory_id.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

DEFAULT_WINDOW_SECONDS = 300  # 5 minutes


@dataclass
class BatchCandidate:
    memory_id: str
    source_id: str
    actor: Optional[str]
    signature: str
    occurred_dt: datetime
    lifecycle_state: str


def assign_batches(
    candidates: list[BatchCandidate], window_seconds: int = DEFAULT_WINDOW_SECONDS
) -> dict[str, str]:
    """Return {memory_id: batch_id} for records that fall into a batch (size >= 2).

    Only records with a real lifecycle transition are eligible — a Figma autosave
    or a git commit ("n/a") is a standalone fact, not part of a state-change batch.
    Within a (source, actor, signature) group, records are chained by time: a gap
    over the window starts a new batch.
    """
    groups: dict[tuple, list[BatchCandidate]] = defaultdict(list)
    for c in candidates:
        if c.lifecycle_state == "n/a":
            continue
        groups[(c.source_id, c.actor, c.signature)].append(c)

    out: dict[str, str] = {}
    for key, items in groups.items():
        items.sort(key=lambda c: c.occurred_dt)
        cluster: list[BatchCandidate] = [items[0]]
        clusters: list[list[BatchCandidate]] = []
        for prev, cur in zip(items, items[1:]):
            if (cur.occurred_dt - prev.occurred_dt).total_seconds() <= window_seconds:
                cluster.append(cur)
            else:
                clusters.append(cluster)
                cluster = [cur]
        clusters.append(cluster)

        for cl in clusters:
            if len(cl) < 2:
                continue  # a lone transition is not a batch — batch_id stays null
            anchor = cl[0]
            seed = f"{key}|{anchor.occurred_dt.isoformat()}|{len(cl)}"
            bid = "batch-" + hashlib.sha256(seed.encode()).hexdigest()[:10]
            for c in cl:
                out[c.memory_id] = bid
    return out
