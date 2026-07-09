"""GitHub adapter — recent commits + issues/PRs per repo. READ-ONLY.

Implemented but the registry source ships disabled (enabled=false) until André
provides repo names. To wire: add "owner/repo" strings to config.repos and set
enabled=true in sources.json.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ..models import Signal
from ..secrets import MissingSecret, resolve
from .base import Adapter, SourceSkipped

_API = "https://api.github.com"


class GitHubAdapter(Adapter):
    type = "github"

    def fetch(self, since: datetime | None, client: httpx.Client) -> list[Signal]:
        repos = self.source.config.get("repos", [])
        if not repos:
            raise SourceSkipped("no repos configured (add 'owner/repo' to config.repos)")

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        # Token is optional: public repos read unauthenticated (lower rate limit).
        # A private repo without a token will surface as a clean HTTP 404/403.
        try:
            headers["Authorization"] = f"Bearer {resolve(self.source.auth['token'])}"
        except MissingSecret:
            pass
        since_iso = since.astimezone(timezone.utc).isoformat() if since else None
        fetched_at = datetime.now(timezone.utc).isoformat()
        signals: list[Signal] = []

        authed = "Authorization" in headers
        for repo in repos:
            # Commits
            params = {"per_page": 30}
            if since_iso:
                params["since"] = since_iso
            r = client.get(f"{_API}/repos/{repo}/commits", headers=headers, params=params)
            if r.status_code in (403, 404):
                hint = (
                    "private repo? set GITHUB_TOKEN in .env"
                    if not authed
                    else "check the token has read access and the owner/repo is correct"
                )
                raise SourceSkipped(f"{repo}: GitHub {r.status_code} — {hint}")
            # 409 = "Git Repository is empty" — a legitimate state (repo has no
            # commits yet), not a failure. Skip commits; issues can still exist.
            if r.status_code != 409:
                r.raise_for_status()
                for c in r.json():
                    msg = (c.get("commit", {}).get("message", "") or "").splitlines()[0]
                    author = c.get("commit", {}).get("author", {}).get("name", "?")
                    signals.append(
                        Signal(
                            source_id=self.source.id,
                            fetched_at=fetched_at,
                            category="job",
                            raw={**c, "_repo": repo},
                            summary=f"GitHub [{repo}] commit: {msg} — {author}",
                        )
                    )

            # Issues + PRs (the issues endpoint returns both)
            iparams = {"state": "all", "per_page": 30, "sort": "updated", "direction": "desc"}
            if since_iso:
                iparams["since"] = since_iso
            ri = client.get(f"{_API}/repos/{repo}/issues", headers=headers, params=iparams)
            ri.raise_for_status()
            for it in ri.json():
                kind = "PR" if "pull_request" in it else "issue"
                signals.append(
                    Signal(
                        source_id=self.source.id,
                        fetched_at=fetched_at,
                        category="job",
                        raw={**it, "_repo": repo},
                        summary=f"GitHub [{repo}] {kind} #{it.get('number')}: "
                        f"{it.get('title', '')} — {it.get('state')}",
                    )
                )
        return signals
