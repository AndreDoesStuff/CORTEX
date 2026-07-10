"""Jira adapter — AXON board, READ-ONLY awareness.

Not a CORTEX-owned task source. This adapter only ever issues GET requests.
Uses the Jira Cloud enhanced search endpoint (/rest/api/3/search/jql).
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ..models import Signal
from ..secrets import resolve
from .base import Adapter, SourceSkipped

_API_BASE = "https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"
_FIELDS = "summary,status,updated,issuetype,assignee,priority,resolution"


class JiraAdapter(Adapter):
    type = "jira"

    def fetch(self, since: datetime | None, client: httpx.Client) -> list[Signal]:
        cfg = self.source.config
        cloud_id = cfg.get("cloud_id")
        project = cfg.get("project_key", "AXON")
        if not cloud_id:
            raise SourceSkipped("no cloud_id configured")

        email = resolve(self.source.auth["email"])
        token = resolve(self.source.auth["token"])

        jql = f"project = {project}"
        if since is not None:
            # Jira JQL accepts "yyyy-MM-dd HH:mm" (interpreted in the account tz).
            stamp = since.astimezone().strftime("%Y-%m-%d %H:%M")
            jql += f' AND updated >= "{stamp}"'
        jql += " ORDER BY updated DESC"

        url = _API_BASE.format(cloud_id=cloud_id) + "/search/jql"
        resp = client.get(
            url,
            params={"jql": jql, "fields": _FIELDS, "maxResults": cfg.get("max_results", 50)},
            auth=(email, token),
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        issues = resp.json().get("issues", [])

        fetched_at = datetime.now(timezone.utc).isoformat()
        signals: list[Signal] = []
        for issue in issues:
            f = issue.get("fields", {})
            key = issue.get("key", "?")
            status = (f.get("status") or {}).get("name", "?")
            updated = f.get("updated", "?")
            summary = f"[{key}] {f.get('summary', '(no title)')} — {status} (updated {updated})"
            signals.append(
                Signal(
                    source_id=self.source.id,
                    fetched_at=fetched_at,
                    category="job",
                    raw=issue,
                    summary=summary,
                )
            )
        return signals
