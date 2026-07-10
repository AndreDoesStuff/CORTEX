"""Answer shaping — the part that matters most.

Turns an Intent + the reused HIPPOCAMPUS `Memory` interface into exactly one
confidence shape. Phrasing follows cortex-phase2-broca-conversation-design
verbatim: brief first, no apologetic padding, no fabricated specifics, and the
confidence is carried in the words (voice has no badge).
"""

from __future__ import annotations

from ..hippocampus.query import Memory
from ..hippocampus.record import MemoryRecord
from .answers import Session, ShapedAnswer
from .intent import Intent

_UNKNOWN = "I don't have anything on that yet."


# ---- factual, no-inference descriptions -------------------------------------
def _terse(mem: Memory, r: MemoryRecord) -> str:
    t = mem.type_of(r.source_id)
    if t == "jira":
        f = r.raw.get("fields", {})
        return f"{r.raw.get('key')} is in {f.get('status', {}).get('name', '?')}"
    if t == "figma":
        return f"a version save on {r.occurred_at[:10]}"
    if t == "github":
        if "commit" in r.raw:
            return f'a commit, "{r.raw["commit"]["message"].splitlines()[0]}"'
        return f"issue #{r.raw.get('number')} ({r.raw.get('state')})"
    return r.summary


def _units(mem: Memory, recs: list[MemoryRecord]) -> list[str]:
    """Collapse batch events into one unit; singles described factually."""
    out, seen = [], set()
    for r in sorted(recs, key=lambda r: r.occurred_at, reverse=True):
        if r.batch_id:
            if r.batch_id in seen:
                continue
            seen.add(r.batch_id)
            members = [x for x in recs if x.batch_id == r.batch_id]
            out.append(f"{len(members)} tickets {members[0].lifecycle_state} "
                       f"in one batch around {r.occurred_at[:10]}")
        else:
            out.append(_terse(mem, r))
    return out


def _unknown() -> ShapedAnswer:
    return ShapedAnswer("unknown", _UNKNOWN)


# ---- per-intent shaping -----------------------------------------------------
def _recent(mem: Memory, intent: Intent) -> ShapedAnswer:
    recs = mem.recent(source_id=intent.source_id, domain=intent.domain)
    if not recs:
        return _unknown()
    units = _units(mem, recs)
    n = len(units)
    if n == 1:
        headline = f"One update on {intent.scope_label}: {units[0]}."
    elif n == 2:
        headline = (f"Two updates on {intent.scope_label} — {units[0]}, "
                    f"and {units[1]}. Want either in detail?")
    else:
        headline = (f"{n} threads of activity on {intent.scope_label}, "
                    f"most recent {recs[0].occurred_at[:10]}. "
                    f"Want the details, or just the headline?")
    detail = mem.render(recs, collapse_batches=True)
    return ShapedAnswer("grounded", headline, detail=detail,
                        spoken=". ".join(units), records=recs)


def _open(mem: Memory, intent: Intent) -> ShapedAnswer:
    recs = mem.open_work(intent.domain)
    if not recs:
        return _unknown()
    n = len(recs)
    if n <= 3:
        items = "; ".join(_terse(mem, r) for r in recs)
        headline = f"{n} open on {intent.domain_label}: {items}."
    else:
        headline = (f"{n} open on {intent.domain_label} right now. "
                    f"Want them listed, or just the count?")
    detail = mem.render(recs, collapse_batches=False)
    return ShapedAnswer("grounded", headline, detail=detail,
                        spoken=headline, records=recs)


def _assess(mem: Memory, intent: Intent) -> ShapedAnswer:
    """Inferred: grounded counts, but the judgment is explicitly flagged."""
    dom = intent.domain
    scoped = [r for r in mem.records if mem.domain_of(r.source_id) == dom]
    if not scoped:
        return _unknown()
    opn = [r for r in scoped if r.lifecycle_state == "open"]
    closed = [r for r in scoped if r.lifecycle_state == "closed"]
    headline = (f"Looks like most of the older work on {intent.domain_label} got "
                f"cleared out — {len(closed)} closed, {len(opn)} still open — but "
                f"that's me reading the counts, not a 'done' status the data sets. "
                f"Want the open ones?")
    detail = mem.render(opn, collapse_batches=False)
    return ShapedAnswer("inferred", headline, detail=detail,
                        spoken=headline, records=opn)


def _comments(mem: Memory, intent: Intent) -> ShapedAnswer:
    """Partial: we hold Figma version history but do NOT pull comments — say so."""
    sid = intent.source_id if (intent.source_id or "").startswith("figma") else None
    recs = mem.recent(source_id=sid, domain="axon") if sid else []
    recs = [r for r in recs if mem.type_of(r.source_id) == "figma"]
    if recs:
        headline = (f"I've got version history for {intent.scope_label} — "
                    f"{len(recs)} saves, last on {recs[0].occurred_at[:10]} — "
                    f"but nothing on comments; I don't pull those yet.")
        detail = mem.render(recs, collapse_batches=True)
        return ShapedAnswer("partial", headline, detail=detail,
                            spoken=headline, records=recs)
    return ShapedAnswer(
        "partial",
        "I don't pull comments from any source yet — only Jira status, Figma "
        "version saves, and GitHub commits.",
    )


def _scope() -> ShapedAnswer:
    return ShapedAnswer(
        "scope",
        "That's prioritization — I don't do that yet. I can tell you what's open "
        "on AXON, or what's changed recently.",
    )


def _more(session: Session) -> ShapedAnswer:
    prev = session.last
    if prev is None or not prev.records:
        return ShapedAnswer("unknown", "Nothing to expand — ask me something first.")
    return ShapedAnswer(prev.shape, "Here's the detail:", detail=prev.detail,
                        spoken=prev.detail, records=prev.records)


def respond(intent: Intent, mem: Memory, session: Session) -> ShapedAnswer:
    if intent.kind == "more":
        return _more(session)
    if intent.kind == "scope":
        return _scope()
    if intent.kind == "respond":
        return _unknown()            # no messaging/response data in any source
    if intent.kind == "comments":
        return _comments(mem, intent)
    if intent.kind == "assess":
        return _assess(mem, intent)
    if intent.kind == "open":
        return _open(mem, intent)
    if intent.kind == "recent":
        return _recent(mem, intent)
    # fallback: best-effort recent; plain unknown if the store has nothing
    return _recent(mem, intent)
