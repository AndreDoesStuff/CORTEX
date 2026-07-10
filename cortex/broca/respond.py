"""Answer shaping — the part that matters most.

Turns an Intent + the reused HIPPOCAMPUS `Memory` interface into exactly one
confidence shape. Phrasing follows cortex-phase2-broca-conversation-design
verbatim: brief first, no apologetic padding, no fabricated specifics, and the
confidence is carried in the words (voice has no badge).
"""

from __future__ import annotations

from ..hippocampus.query import Memory
from ..hippocampus.record import MemoryRecord
from . import banks
from .answers import Session, ShapedAnswer
from .intent import Intent


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


def _clean_citations(mem: Memory, recs: list[MemoryRecord]) -> list[str]:
    """Citations the narrator may safely voice — Jira keys and GitHub issue
    numbers only. Figma version ids and commit shas stay in `records` metadata
    (provenance is preserved) but are kept out of the packet so their long digit
    runs can't trip fact-validation."""
    out: list[str] = []
    for r in recs:
        t = mem.type_of(r.source_id)
        if t == "jira" and r.raw.get("key"):
            out.append(r.raw["key"])
        elif t == "github" and "commit" not in r.raw and r.raw.get("number") is not None:
            out.append(f"#{r.raw['number']}")
    seen: list[str] = []
    for c in out:
        if c not in seen:
            seen.append(c)
    return seen[:10]


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
    return ShapedAnswer("unknown", banks.pick(banks.UNKNOWN))


# ---- per-intent shaping -----------------------------------------------------
def _recent(mem: Memory, intent: Intent) -> ShapedAnswer:
    recs = mem.recent(source_id=intent.source_id, domain=intent.domain)
    if not recs:
        return _unknown()
    units = _units(mem, recs)
    n = len(units)
    if n == 1:
        headline = banks.pick(banks.RECENT_SINGLE, item=units[0], scope=intent.scope_label)
    else:
        headline = banks.pick(banks.RECENT_MULTI, count_phrase=f"{n} updates",
                              scope=intent.scope_label, date=recs[0].occurred_at[:10])
    detail = mem.render(recs, collapse_batches=True)
    values = {"count": n, "scope": intent.scope_label,
              "most_recent_date": recs[0].occurred_at[:10],
              "citations": _clean_citations(mem, recs)}
    return ShapedAnswer("grounded", headline, detail=detail,
                        spoken=". ".join(units), records=recs, values=values)


def _open(mem: Memory, intent: Intent) -> ShapedAnswer:
    recs = mem.open_work(intent.domain)
    if not recs:
        return _unknown()
    headline = banks.pick(banks.OPEN, count=len(recs), domain=intent.domain_label)
    detail = mem.render(recs, collapse_batches=False)
    values = {"count": len(recs), "domain": intent.domain_label,
              "citations": _clean_citations(mem, recs)}
    return ShapedAnswer("grounded", headline, detail=detail,
                        spoken=headline, records=recs, values=values)


def _assess(mem: Memory, intent: Intent) -> ShapedAnswer:
    """Inferred: grounded counts, but the judgment is explicitly flagged."""
    dom = intent.domain
    scoped = [r for r in mem.records if mem.domain_of(r.source_id) == dom]
    if not scoped:
        return _unknown()
    opn = [r for r in scoped if r.lifecycle_state == "open"]
    closed = [r for r in scoped if r.lifecycle_state == "closed"]
    headline = banks.pick(banks.INFERRED, closed=len(closed), open_count=len(opn),
                          domain=intent.domain_label)
    detail = mem.render(opn, collapse_batches=False)
    values = {"closed": len(closed), "open_count": len(opn), "domain": intent.domain_label,
              "citations": _clean_citations(mem, opn)}
    return ShapedAnswer("inferred", headline, detail=detail,
                        spoken=headline, records=opn, values=values)


def _comments(mem: Memory, intent: Intent) -> ShapedAnswer:
    """Partial: we hold Figma version history but do NOT pull comments — say so."""
    sid = intent.source_id if (intent.source_id or "").startswith("figma") else None
    recs = mem.recent(source_id=sid, domain="axon") if sid else []
    recs = [r for r in recs if mem.type_of(r.source_id) == "figma"]
    if recs:
        headline = banks.pick(banks.PARTIAL, count=len(recs), scope=intent.scope_label,
                              date=recs[0].occurred_at[:10])
        detail = mem.render(recs, collapse_batches=True)
        values = {"count": len(recs), "scope": intent.scope_label,
                  "most_recent_date": recs[0].occurred_at[:10]}
        return ShapedAnswer("partial", headline, detail=detail,
                            spoken=headline, records=recs, values=values)
    return ShapedAnswer(
        "partial",
        "I don't pull comments from any source yet — only Jira status, Figma "
        "version saves, and GitHub commits.",
    )


def _scope(intent: Intent) -> ShapedAnswer:
    capability = "task creation" if "task" in intent.question.lower() else "prioritization"
    alternative = "what's open on AXON, or what's changed recently"
    return ShapedAnswer("scope", banks.pick(banks.SCOPE, capability=capability,
                                            alternative=alternative),
                        values={"capability": capability, "alternative": alternative})


def _conversational(intent: Intent) -> ShapedAnswer:
    bank = {
        "greeting": banks.GREETING,
        "gratitude": banks.GRATITUDE,
        "capability": banks.CAPABILITY,
        "banter": banks.BANTER,
    }.get(intent.sub, banks.BANTER)
    return ShapedAnswer("conversational", banks.pick(bank))


def _more(session: Session) -> ShapedAnswer:
    prev = session.last
    if prev is None or not prev.records:
        return ShapedAnswer("unknown", "Nothing to expand — ask me something first.")
    return ShapedAnswer(prev.shape, "Here's the detail:", detail=prev.detail,
                        spoken=prev.detail, records=prev.records)


def respond(intent: Intent, mem: Memory, session: Session) -> ShapedAnswer:
    if intent.kind == "more":
        return _more(session)
    if intent.kind == "conversational":
        return _conversational(intent)
    if intent.kind == "scope":
        return _scope(intent)
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
