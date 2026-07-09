"""Notion adapter — recently edited pages/databases shared with the integration.
READ-ONLY. Lower priority (wire last); source ships disabled.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ..models import Signal
from ..secrets import resolve
from .base import Adapter

_API = "https://api.notion.com/v1"
_VERSION = "2022-06-28"


def _title_of(obj: dict) -> str:
    """Best-effort page title extraction from Notion's property soup."""
    props = obj.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            parts = prop.get("title", [])
            return "".join(p.get("plain_text", "") for p in parts) or "(untitled)"
    return obj.get("id", "(untitled)")


class NotionAdapter(Adapter):
    type = "notion"

    def fetch(self, since: datetime | None, client: httpx.Client) -> list[Signal]:
        token = resolve(self.source.auth["token"])
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _VERSION,
            "Content-Type": "application/json",
        }
        body = {
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            "page_size": 50,
        }
        resp = client.post(f"{_API}/search", headers=headers, json=body)
        resp.raise_for_status()
        results = resp.json().get("results", [])

        fetched_at = datetime.now(timezone.utc).isoformat()
        signals: list[Signal] = []
        for obj in results:
            edited = obj.get("last_edited_time", "")
            if since is not None and edited:
                try:
                    if datetime.fromisoformat(edited.replace("Z", "+00:00")) < since:
                        continue
                except ValueError:
                    pass
            title = _title_of(obj)
            summary = f"Notion {obj.get('object', 'page')}: {title} (edited {edited})"
            signals.append(
                Signal(
                    source_id=self.source.id,
                    fetched_at=fetched_at,
                    category="fyi",
                    raw=obj,
                    summary=summary,
                )
            )
        return signals
