"""CORTEX Phase 1 — HIPPOCAMPUS: append-only, immutable grounded memory.

Answers "what happened" (with citations), never "what should I do" (that's
PREFRONTAL, Phase 3). Never edits or deletes a record — a ticket closing is a
new appended fact, not a mutation of the old one.
"""

__all__ = ["record", "store", "ingest", "query"]
