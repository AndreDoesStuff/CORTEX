"""BROCA entrypoint — text-in, voice-out (Phase 2a).

    broca "what's open on AXON right now?"     # ask once
    broca                                       # interactive session
    broca --no-voice "..."                      # print only (no say)

Reactive only: BROCA never speaks unless asked. Read-only against HIPPOCAMPUS.
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from ..hippocampus.query import Memory
from ..hippocampus.store import MemoryStore
from ..registry import load_sources
from . import banks
from .answers import Session
from .intent import classify
from .narrator import narrate
from .respond import respond
from .voice import available as voice_available
from .voice import speak

_DEFAULT_STORE = os.environ.get("HIPPOCAMPUS_STORE", "hippocampus_memory.jsonl")

# how the shape reads on screen (voice carries it in the words already)
_TAG = {"grounded": "grounded", "inferred": "inferred", "unknown": "unknown",
        "partial": "partial", "scope": "—"}


def _handle(q, mem, session, no_voice, voice_file, trace=False):
    intent = classify(q)
    ans = respond(intent, mem, session)

    # Narration: hand the fact packet to the LLM, validate, fall back to the
    # template on any failure. "more" is a deterministic citation dump — not narrated.
    source = "template"
    if intent.kind != "more":
        text, source = narrate(ans.shape, ans.values, q, ans.headline)
        ans.headline = text
        ans.spoken = text
        session.last = ans

    print(f"\nCORTEX [{_TAG.get(ans.shape, ans.shape)}]: {ans.headline}")
    if trace and intent.kind != "more":
        print(f"   (narration: {source})")
    if intent.kind == "more" and ans.detail:
        print(ans.detail)
    elif ans.records:
        print(f"   ({len(ans.records)} cited memories — say 'details' to see them)")

    speak(ans.voice_text(), enabled=not no_voice, out_file=voice_file)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="broca", description="BROCA — talk to CORTEX memory (Phase 2a).")
    ap.add_argument("question", nargs="*", help="ask once and exit; omit for interactive")
    ap.add_argument("--store", default=_DEFAULT_STORE, help="HIPPOCAMPUS memory log")
    ap.add_argument("--config", default="sources.json", help="source registry")
    ap.add_argument("--no-voice", action="store_true", help="print only, don't speak")
    ap.add_argument("--voice-file", help="write spoken audio to this .aiff (for testing)")
    ap.add_argument("--seed", type=int, help="pin fallback phrasing-variant selection")
    ap.add_argument("--trace", action="store_true", help="print narration source (llm/fallback)")
    ap.add_argument("--listen", action="store_true",
                    help="capture one spoken question from the mic (Phase 2b)")
    args = ap.parse_args(argv)

    # Load .env so VOICEBOX_PROFILE_NAME (voice) and ANTHROPIC_API_KEY (narrator)
    # are visible. override=False: an inline env var still wins over .env.
    load_dotenv()

    seed = args.seed if args.seed is not None else os.environ.get("BROCA_SEED")
    if seed is not None:
        banks.seed(int(seed))

    sources = load_sources(args.config)
    mem = Memory(MemoryStore(args.store), sources)
    session = Session()

    if args.listen:
        from .listen import listen
        print("🎤 listening — speak your question…", file=sys.stderr)
        q = listen()
        if not q:
            print("(didn't catch anything — mic off, silent, or permission denied)",
                  file=sys.stderr)
            return 0
        print(f'you said: "{q}"')
        _handle(q, mem, session, args.no_voice, args.voice_file, args.trace)
        return 0

    if args.question:
        _handle(" ".join(args.question), mem, session, args.no_voice, args.voice_file, args.trace)
        return 0

    voice_note = "voice on" if (voice_available() and not args.no_voice) else "text only"
    print(f"BROCA — ask about AXON / CORTEX memory ({voice_note}). Ctrl-D or 'exit' to quit.")
    while True:
        try:
            q = input("\nyou> ").strip()
        except EOFError:
            break
        if not q:
            continue
        if q.lower() in {"quit", "exit"}:
            break
        _handle(q, mem, session, args.no_voice, args.voice_file, args.trace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
