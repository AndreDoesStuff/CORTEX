"""Figma adapter — version activity ("what changed") on a file/branch. READ-ONLY."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ..models import Signal
from ..secrets import resolve
from .base import Adapter, SourceSkipped

_API = "https://api.figma.com/v1"


def _parse_iso(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class FigmaAdapter(Adapter):
    type = "figma"

    def fetch(self, since: datetime | None, client: httpx.Client) -> list[Signal]:
        cfg = self.source.config
        file_key = cfg.get("file_key")
        if not file_key:
            raise SourceSkipped("no file_key configured")

        token = resolve(self.source.auth["token"])

        resp = client.get(
            f"{_API}/files/{file_key}/versions",
            headers={"X-Figma-Token": token},
        )
        resp.raise_for_status()
        versions = resp.json().get("versions", [])

        fetched_at = datetime.now(timezone.utc).isoformat()
        label = cfg.get("label", file_key)
        signals: list[Signal] = []
        for v in versions:
            created = v.get("created_at", "")
            if since is not None:
                ts = _parse_iso(created)
                if ts is not None and ts < since:
                    continue
            v = {**v, "_file_key": file_key}  # provenance anchor inside raw
            user = (v.get("user") or {}).get("handle", "?")
            name = v.get("label") or v.get("description") or "(autosave)"
            summary = f"Figma [{label}] version '{name}' by {user} at {created}"
            signals.append(
                Signal(
                    source_id=self.source.id,
                    fetched_at=fetched_at,
                    category="fyi",
                    raw=v,
                    summary=summary,
                )
            )
        return signals
