"""CORTEX Phase 2 — BROCA: language production.

A reactive, read-only conversation loop over HIPPOCAMPUS. Every answer carries
its confidence IN THE WORDS (grounded / inferred / unknown), never blended.
No task talk, no prioritization, no writes, no proactive contact. Phase 2a is
text-in / voice-out; 2b adds speech input later with the same downstream pipeline.
"""

__all__ = ["intent", "respond", "voice", "answers"]
