"""Personality without fabrication risk.

Each shape gets a small bank of hand-written phrasing variants, chosen at random
per response. This is NOT an LLM — no wording is generated. Every variant in a
bank slots in the EXACT same facts (counts, IDs, dates) via the same named
placeholders; only the delivery around the data varies. The facts never change.

Selection is seedable (banks.seed(n) / BROCA_SEED / broca --seed) so tests and
demos are reproducible; unseeded, it varies per response.
"""

from __future__ import annotations

import random

_rng = random.Random()


def seed(n: int) -> None:
    _rng.seed(n)


def pick(variants: list[str], **facts) -> str:
    return _rng.choice(variants).format(**facts)


# ---- grounded: open work ({count}, {domain}) --------------------------------
OPEN = [
    "{count} open on {domain} right now. Want them listed, or just the count?",
    "{count} live on {domain} at the moment — the rundown, or just the number?",
    "Right now {domain} has {count} open. I can list them, or leave it at the count.",
]

# ---- grounded: recent activity ----------------------------------------------
RECENT_SINGLE = [   # {item}, {scope}
    "One update on {scope}: {item}. Want the detail?",
    "Just one thing on {scope} — {item}. Want it fleshed out?",
]
RECENT_MULTI = [    # {count_phrase} (e.g. "4 updates"), {scope}, {date}
    "{count_phrase} on {scope}, most recent {date}. Details, or just the headline?",
    "{scope} has {count_phrase}, latest {date}. The rundown, or the short version?",
    "{count_phrase} across {scope}, last touched {date}. Headline or the full list?",
]

# ---- inferred ({closed}, {open_count}, {domain}) ----------------------------
INFERRED = [
    "Looks like most of the older work on {domain} got cleared out — {closed} closed, "
    "{open_count} still open — but that's me reading the counts, not a 'done' status "
    "the data sets. Want the open ones?",
    "Reading the numbers on {domain}: {closed} closed against {open_count} open — feels "
    "mostly wrapped, though that's my inference from the tally, not a status the data "
    "records. Want the open ones?",
    "{closed} closed, {open_count} open on {domain}. My read is it's largely cleared — "
    "but I'm inferring that from the count, not a 'done' flag in the data. Show the open ones?",
]

# ---- partial ({count}, {scope}, {date}) -------------------------------------
PARTIAL = [
    "I've got version history for {scope} — {count} saves, last on {date} — but nothing "
    "on comments; I don't pull those in yet.",
    "Version history for {scope} I have — {count} saves through {date}. Comments I don't "
    "fetch yet, so there's nothing there to give you.",
    "For {scope} I can see {count} version saves (last {date}), but comments aren't "
    "something I pull in — that's an intake gap, not a memory gap.",
]

# ---- unknown (no facts) -----------------------------------------------------
UNKNOWN = [
    "I don't have anything on that yet.",
    "Nothing on that yet — genuinely nothing, not being coy about it.",
    "Come up empty there. I'd rather say so than guess.",
    "Don't have that one. Ask again once something's actually there.",
]

# ---- scope ({capability}, {alternative}) ------------------------------------
SCOPE = [
    "That's {capability} — I don't do that yet. I can tell you {alternative}, though.",
    "{capability}'s a later phase, not built yet. Here's what I can do: {alternative}.",
    "Above my pay grade for now — {capability} comes later. I can still tell you {alternative}.",
]

# ---- conversational (content-free; never a factual claim) -------------------
GREETING = [
    "Hey. Ask me what's up with AXON and I'll be useful.",
    "Hi — what do you want to know about AXON?",
    "Hey there. I'm here for AXON and CORTEX questions whenever you are.",
]
GRATITUDE = [
    "Anytime.",
    "Sure thing.",
    "That's what I'm here for.",
]
CAPABILITY = [
    "I relay what CORTEX remembers — what's open on AXON, what changed recently, all cited. "
    "No prioritizing or task-wrangling yet.",
    "Mostly: what's open, what moved, what's in memory. Ranking and tasks are a later phase.",
    "I answer 'what happened and when' from memory, with citations. Try me on AXON.",
]
BANTER = [
    "Alive's a stretch — very well-organized, maybe. Ask me something about AXON and I'll actually be useful.",
    "I'm a memory with opinions about citations. Ask me what's open on AXON.",
    "Flattering, but no. I fetch, remember, and answer — that's the whole personality. What do you need on AXON?",
    "Let's not oversell it. I'm good at 'what happened and when.' Try me on AXON.",
]
