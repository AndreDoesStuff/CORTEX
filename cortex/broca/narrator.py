"""LLM narration layer (Phase 2 narrator design).

Builds a closed **fact packet** (shape + a fixed set of values), asks
claude-haiku-4-5 to narrate ONLY those facts naturally, then validates every
number / date / ticket-ID token in the output against the packet. On any
mismatch — or any missing key, network, or API failure — it falls back to the
deterministic template bank for that shape. Never retries silently, never
speaks unvalidated output, never fails with dead air.

Everything upstream (classify -> query HIPPOCAMPUS -> shape) is unchanged; the
six shapes and their meaning are unchanged. Only how the words get chosen changes.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Optional

MODEL = "claude-haiku-4-5"

# System-prompt constraints — copied VERBATIM from
# cortex-phase2-broca-narrator-layer-design-v0.1.0.md (§ The narration call).
# Do not paraphrase the four bullets.
_CONSTRAINTS = """- Narrate only the values given. Never introduce a number, date, name, or ticket ID that isn't in `values`.
- Never claim more confidence than the shape allows — a `grounded` shape can state values as fact; an `unknown` shape must say plainly that nothing was found, with no hedging that implies partial knowledge; an `inferred` shape must explicitly flag the interpretive leap; `conversational` must not reference AXON/CORTEX data at all, even if it seems relevant.
- Keep it brief — this is spoken aloud, not read.
- If asked to elaborate beyond what `values` contains, say so plainly rather than inventing detail."""

_SYSTEM = (
    "You are BROCA, the voice of CORTEX. You narrate one short spoken line from a "
    "fact packet. These constraints are absolute:\n" + _CONSTRAINTS
)

# Shape guidance for the two shapes the verbatim constraints don't name.
_SHAPE_HINT = {
    "partial": ("`partial`: state what the values cover, then say plainly that the rest "
                "(e.g. comments) isn't collected yet — never imply you have it."),
    "scope": ("`scope`: say plainly this capability doesn't exist yet; offer the "
              "alternative if given. Make no claim about AXON/CORTEX data."),
}

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TICKET = re.compile(r"\b[A-Za-z]{2,}-\d+\b")
_HASHNUM = re.compile(r"#\d+")
_NUM = re.compile(r"\d+")


def build_packet(shape: str, values: dict[str, Any]) -> dict[str, Any]:
    return {"shape": shape, "values": values}


def _allowed(values: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    nums, dates, ids = set(), set(), set()
    for v in values.values():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            nums.add(str(v))
        elif isinstance(v, str) and _DATE.fullmatch(v):
            dates.add(v)
    for c in values.get("citations", []) or []:
        for m in _TICKET.findall(c):
            ids.add(m.upper())
        for m in _HASHNUM.findall(c):
            ids.add(m)
    return nums, dates, ids


def validate(text: str, values: dict[str, Any]) -> bool:
    """True iff every number/date/ticket-ID token in `text` exists in `values`.

    Dates and IDs are stripped before bare-number checking so the digits inside
    them (a year, a ticket number) don't trip the number check.
    """
    nums, dates, ids = _allowed(values)
    for d in _DATE.findall(text):
        if d not in dates:
            return False
    stripped = _DATE.sub(" ", text)
    for tok in _TICKET.findall(stripped):
        if tok.upper() not in ids:
            return False
    stripped = _TICKET.sub(" ", stripped)
    for tok in _HASHNUM.findall(stripped):
        if tok not in ids:
            return False
    stripped = _HASHNUM.sub(" ", stripped)
    for n in _NUM.findall(stripped):
        if n not in nums:
            return False
    return True


def _call_llm(packet: dict, question: str, client_factory: Optional[Callable]) -> Optional[str]:
    import anthropic  # lazy: absence -> ImportError -> fallback

    client = client_factory() if client_factory else anthropic.Anthropic()
    hint = _SHAPE_HINT.get(packet["shape"], "")
    user = (
        f"Fact packet:\n{json.dumps(packet, ensure_ascii=False)}\n\n"
        f"The user asked: {question!r}\n"
        + (hint + "\n" if hint else "")
        + "Narrate the answer as one brief spoken line."
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return None


def narrate(
    shape: str,
    values: dict[str, Any],
    question: str,
    fallback: str,
    *,
    client_factory: Optional[Callable] = None,
) -> tuple[str, str]:
    """Return (spoken_text, source). source is "llm" or "fallback:<reason>".

    The fallback is the shape's proven deterministic template — not a downgrade,
    just the path you won't usually hear.
    """
    # No credential -> don't import the SDK or build a doomed request. This skips
    # ~1-2s of wasted work per answer when narration isn't configured. (When a
    # client_factory is injected, e.g. in tests, honor it regardless.)
    if client_factory is None and not (
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    ):
        return fallback, "fallback:no-key"
    try:
        text = _call_llm(build_packet(shape, values), question, client_factory)
    except Exception as e:  # ImportError / auth / network / API — all degrade
        return fallback, f"fallback:{type(e).__name__}"
    if not text or not text.strip():
        return fallback, "fallback:empty"
    text = text.strip()
    if not validate(text, values):
        return fallback, "fallback:validation"
    return text, "llm"
