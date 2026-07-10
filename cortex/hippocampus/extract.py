"""Per-source-type extraction from a THALAMUS `raw` payload.

Every value here comes from an EXPLICIT, machine-readable field in `raw`.
Nothing is inferred from titles or free text — that rule is the whole point of
keeping HIPPOCAMPUS grounded (a "OBSOLETE:" title prefix is text, not a field).
"""

from __future__ import annotations

from typing import Any, Optional

# statusCategory.key splits open (new/indeterminate) from done. Within "done",
# an explicit `resolution` VALUE distinguishes obsolete/abandoned closes from
# genuine completions. This is the only obsolete signal we honor — the
# "OBSOLETE:" title text is NOT a field and is never matched on.
_JIRA_LIFECYCLE = {"new": "open", "indeterminate": "open", "done": "closed"}

# Explicit Jira resolution values that mean "closed without completing" -> obsolete.
_JIRA_OBSOLETE_RESOLUTIONS = {
    "won't do", "wont do", "won't fix", "wont fix", "obsolete", "duplicate",
    "cannot reproduce", "declined", "abandoned", "as designed", "invalid",
}


def occurred_at(stype: str, raw: dict[str, Any], fallback: str) -> str:
    if stype == "jira":
        return raw.get("fields", {}).get("updated") or fallback
    if stype == "figma":
        return raw.get("created_at") or fallback
    if stype == "github":
        if "commit" in raw:
            return raw["commit"].get("committer", {}).get("date") or fallback
        return raw.get("updated_at") or fallback
    return fallback


def entity_key(stype: str, raw: dict[str, Any]) -> str:
    if stype == "jira":
        return str(raw.get("key", raw.get("id", "?")))
    if stype == "figma":
        return f"{raw.get('_file_key', '?')}:{raw.get('id', '?')}"
    if stype == "github":
        if "commit" in raw:
            return str(raw.get("sha", "?"))
        return f"issue:{raw.get('id', raw.get('number', '?'))}"
    return "?"


def lifecycle_state(stype: str, raw: dict[str, Any]) -> str:
    if stype == "jira":
        fields = raw.get("fields", {})
        key = fields.get("status", {}).get("statusCategory", {}).get("key")
        if key == "done":
            resolution = (fields.get("resolution") or {}).get("name", "")
            if resolution.strip().lower() in _JIRA_OBSOLETE_RESOLUTIONS:
                return "obsolete"
            return "closed"
        return _JIRA_LIFECYCLE.get(key, "n/a")
    if stype == "github" and "commit" not in raw and "state" in raw:
        # a GitHub issue/PR — open/closed is an explicit field
        return {"open": "open", "closed": "closed"}.get(raw["state"], "n/a")
    # Figma versions, GitHub commits: facts that happened, not open/closed things
    return "n/a"


def actor(stype: str, raw: dict[str, Any]) -> Optional[str]:
    """Opaque actor id for batch clustering. Never displayed (avoids PII)."""
    if stype == "figma":
        u = raw.get("user") or {}
        return u.get("id") or u.get("handle")
    if stype == "github":
        if "commit" in raw:
            return (raw.get("author") or {}).get("login")
        return (raw.get("user") or {}).get("login")
    # Jira's basic payload carries no per-change actor (would need the changelog)
    return None


def batch_signature(stype: str, raw: dict[str, Any], lifecycle: str) -> str:
    """What state transition this record represents — records sharing a
    signature (+ actor + tight time window) are one real-world batch event."""
    if stype == "jira":
        return "to:" + str(raw.get("fields", {}).get("status", {}).get("name", "?"))
    if stype == "github":
        return "issue-state:" + str(raw.get("state", "?"))
    return lifecycle


def entity_ref(stype: str, raw: dict[str, Any]) -> str:
    """Human-readable provenance pointer for citations (no PII)."""
    if stype == "jira":
        return f"jira:{raw.get('key', '?')}"
    if stype == "figma":
        return f"figma-version:{raw.get('id', '?')}@{raw.get('_file_key', '?')}"
    if stype == "github":
        if "commit" in raw:
            return f"commit:{str(raw.get('sha', ''))[:10]}"
        return f"gh-issue:#{raw.get('number', '?')}"
    return "?"
