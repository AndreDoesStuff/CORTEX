"""Map a typed question to an intent + which HIPPOCAMPUS query to run.

Deterministic keyword routing — no LLM, so nothing here can invent a fact. All
actual data comes from the reused `Memory` query interface; this file only picks
WHICH query and target, never fabricates content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# order matters: earlier kinds win when phrases overlap
_MORE = ("tell me more", "the details", "details", "expand", "go on",
         "list them", "full list", "list it", "more")
_SCOPE = ("focus on", "prioriti", "what should i", "most important",
          "create a task", "add a task", "make a task", "remind me",
          "assign", "send an", "draft ", "should i work")
_RESPOND = ("respond", "replied", "reply", "responded", "hear back",
            "get back", "answer the", "acknowledge")
_COMMENTS = ("comment", "feedback on", "review note")
_ASSESS = ("almost done", "is it done", "are we done", "how's", "how is",
           "how far", "on track", "wrapping up", "nearly done", "close to done",
           "how are we doing", "how's it going", "make progress", "progressing")
_OPEN = ("what's open", "whats open", "still open", "what's active", "active",
         "outstanding", "remaining", "left to do", "on the board", "what's left",
         "whats left", "in flight", "open on")
_RECENT = ("what's up", "whats up", "what's new", "whats new", "what happened",
           "any updates", "anything on", "latest", "recently", "this week",
           "today", "what's going on", "whats going on", "news", "update on")

# Conversational routing (shape 6). Deliberately conservative: only fires when
# there is NO plausible mapping to a real HIPPOCAMPUS query (the doc's guardrail).
_GREETINGS = {"hi", "hey", "hello", "yo", "howdy", "sup"}
_BANTER = ("alive", "conscious", "sentient", "are you real", "are you human",
           "do you feel", "do you dream", "do you sleep", "have feelings",
           "who are you", "what are you", "your name", "who made you",
           "who built you", "tell me a joke", "how are you", "are you ok",
           "are you there", "do you think", "do you have")
_CAPABILITY = ("what can you do", "what do you do", "how do you work",
               "what are you for", "capabilities", "what can i ask")
# signals that a question DOES map to a real query — suppresses conversational
_QUERY_WORDS = ("axon", "jira", "ticket", "figma", "table", "main branch",
                "github", "repo", "commit", "open", "recent", "happen", "comment",
                "closed", "status", "branch", "update", "backlog", "in progress",
                "outstanding", "active", "left to do", "design", "vertebra")


def _query_like(ql: str) -> bool:
    return any(w in ql for w in _QUERY_WORDS)


def _conversational_sub(ql: str) -> Optional[str]:
    first = ql.split()[0] if ql.split() else ""
    if first in _GREETINGS or ql.startswith(("good morning", "good evening", "good afternoon")):
        return "greeting"
    if "thank" in ql or "cheers" in ql or "appreciate" in ql:
        return "gratitude"
    if ql.strip() in {"help", "help me"} or any(p in ql for p in _CAPABILITY):
        return "capability"
    if any(p in ql for p in _BANTER):
        return "banter"
    return None


@dataclass
class Intent:
    kind: str                 # more|conversational|scope|respond|comments|assess|open|recent|fallback
    source_id: Optional[str]
    domain: Optional[str]
    scope_label: str          # e.g. "the table branch", "AXON"
    domain_label: str         # e.g. "AXON", "the CORTEX repo"
    question: str
    sub: str = ""             # conversational sub-type: greeting|gratitude|capability|banter


def _resolve_target(ql: str):
    if "table" in ql:
        return "figma-axon-table", "axon", "the table branch", "AXON"
    if "main branch" in ql or "main design" in ql:
        return "figma-axon-main", "axon", "the main branch", "AXON"
    if "commit" in ql or "github" in ql or "the repo" in ql or "cortex code" in ql:
        return "github-cortex", "cortex-self", "the CORTEX repo", "the CORTEX repo"
    if "jira" in ql or "ticket" in ql:
        return "jira-axon", "axon", "the AXON tickets", "AXON"
    if "cortex" in ql or "my code" in ql:
        return "github-cortex", "cortex-self", "the CORTEX repo", "the CORTEX repo"
    if "figma" in ql or "design" in ql:
        return None, "axon", "the AXON design files", "AXON"
    return None, "axon", "AXON", "AXON"  # default domain


def _has(ql: str, phrases) -> bool:
    return any(p in ql for p in phrases)


def classify(question: str) -> Intent:
    ql = question.lower().strip()
    sid, dom, scope, dlabel = _resolve_target(ql)
    sub = ""

    conv = _conversational_sub(ql)
    if _has(ql, _MORE):
        kind = "more"
    elif conv and not _query_like(ql):
        # banter / self-reference with no plausible real query -> personality is safe
        kind, sub = "conversational", conv
    elif _has(ql, _SCOPE):
        kind = "scope"
    elif _has(ql, _RESPOND):
        kind = "respond"
    elif _has(ql, _COMMENTS):
        kind = "comments"
    elif _has(ql, _ASSESS):
        kind = "assess"
    elif _has(ql, _OPEN):
        kind = "open"
    elif _has(ql, _RECENT):
        kind = "recent"
    else:
        kind = "fallback"

    return Intent(kind=kind, source_id=sid, domain=dom,
                  scope_label=scope, domain_label=dlabel, question=question, sub=sub)
