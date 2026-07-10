"""Source registry (Deliverable 1): loads sources.json into typed configs and
maps each to its adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SourceConfig:
    id: str
    type: str
    enabled: bool
    cadence: str
    trust_level: str
    auth: dict[str, str]
    scope: str
    # HIPPOCAMPUS joins against this at query time (e.g. "axon" vs "cortex-self")
    # instead of duplicating domain into every memory record.
    domain: str = "unknown"
    config: dict[str, Any] = field(default_factory=dict)


def load_sources(path: str | Path) -> list[SourceConfig]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = data.get("sources", [])
    sources: list[SourceConfig] = []
    for e in entries:
        sources.append(
            SourceConfig(
                id=e["id"],
                type=e["type"],
                enabled=bool(e.get("enabled", True)),
                cadence=e.get("cadence", "on-demand"),
                trust_level=e.get("trust_level", "unknown"),
                auth=e.get("auth", {}),
                scope=e.get("scope", ""),
                domain=e.get("domain", "unknown"),
                config=e.get("config", {}),
            )
        )
    return sources
