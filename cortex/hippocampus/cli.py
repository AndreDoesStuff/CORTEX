"""HIPPOCAMPUS entrypoint: ingest THALAMUS signal into the memory log, and run
grounded, cited queries against it.

    hippocampus ingest --snapshot snapshot-2026-07-09.json
    hippocampus ingest --live --since 2026-06-09T00:00:00Z
    hippocampus query --open --domain axon
    hippocampus query --recent --source figma-axon-table --since 2026-06-09
    hippocampus stats
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from .ingest import collect_live, load_registry, signals_to_records
from .query import Memory
from .record import parse_dt
from .store import MemoryStore

_DEFAULT_STORE = os.environ.get("HIPPOCAMPUS_STORE", "hippocampus_memory.jsonl")


def _parse_since(value):
    if not value:
        return None
    try:
        return parse_dt(value)
    except ValueError:
        sys.exit(f"error: --since must be ISO8601, got {value!r}")


def _cmd_ingest(args) -> int:
    sources = load_registry(args.config)
    if args.snapshot:
        with open(args.snapshot, encoding="utf-8") as f:
            signals = json.load(f)
        print(f"loaded {len(signals)} signals from {args.snapshot}", file=sys.stderr)
    elif args.live:
        from dotenv import load_dotenv

        load_dotenv()
        signals, skipped, errored = collect_live(sources, _parse_since(args.since))
        print(f"pulled {len(signals)} signals live", file=sys.stderr)
        if skipped:
            print(f"skipped: {'; '.join(skipped)}", file=sys.stderr)
        if errored:
            print(f"errors:  {'; '.join(errored)}", file=sys.stderr)
    else:
        sys.exit("error: ingest needs --snapshot FILE or --live")

    records = signals_to_records(signals, sources)
    store = MemoryStore(args.store)
    added = store.append(records)
    batched = len({r.batch_id for r in records if r.batch_id})
    print(f"ingested: {added} new records appended ({len(records) - added} already present); "
          f"{batched} batch event(s) detected. store={args.store}")
    return 0


def _cmd_query(args) -> int:
    sources = load_registry(args.config)
    mem = Memory(MemoryStore(args.store), sources)

    if args.open:
        if not args.domain:
            sys.exit("error: --open requires --domain")
        results = mem.open_work(args.domain)
        print(f'"What\'s open on {args.domain} right now?" — {len(results)} live record(s)\n')
        print(mem.render(results, collapse_batches=False))  # show each active item
    elif args.recent:
        results = mem.recent(source_id=args.source, domain=args.domain,
                             since=_parse_since(args.since))
        scope = args.source or args.domain or "all sources"
        print(f'"Recent activity — {scope}" — {len(results)} record(s)\n')
        print(mem.render(results))
    else:
        sys.exit("error: query needs --open or --recent")
    return 0


def _cmd_stats(args) -> int:
    sources = load_registry(args.config)
    mem = Memory(MemoryStore(args.store), sources)
    recs = mem.records
    print(f"memory store: {args.store}  ·  {len(recs)} records")
    print("\nby source (domain):")
    for sid, n in Counter(r.source_id for r in recs).most_common():
        print(f"  {sid:<18} {n:>4}   domain={mem.domain_of(sid)}")
    print("\nby lifecycle_state:")
    for st, n in Counter(r.lifecycle_state for r in recs).most_common():
        print(f"  {st:<10} {n:>4}")
    print("\nby signal_category:")
    for c, n in Counter(r.signal_category for r in recs).most_common():
        print(f"  {c:<10} {n:>4}")
    batches = Counter(r.batch_id for r in recs if r.batch_id)
    print(f"\nbatch events: {len(batches)}")
    for bid, n in batches.most_common():
        print(f"  {bid}  {n} records")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="hippocampus", description=__doc__)
    p.add_argument("--config", default="sources.json", help="source registry path")
    p.add_argument("--store", default=_DEFAULT_STORE, help="memory log path (JSONL)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest", help="append THALAMUS signal into memory")
    pi.add_argument("--snapshot", help="ingest a saved THALAMUS JSON snapshot")
    pi.add_argument("--live", action="store_true", help="pull live via THALAMUS")
    pi.add_argument("--since", help="ISO8601 lower bound for --live")
    pi.set_defaults(func=_cmd_ingest)

    pq = sub.add_parser("query", help="grounded, cited query")
    pq.add_argument("--open", action="store_true", help="live work (lifecycle=open)")
    pq.add_argument("--recent", action="store_true", help="recent activity")
    pq.add_argument("--domain", help="filter by source domain (e.g. axon)")
    pq.add_argument("--source", help="filter by source id")
    pq.add_argument("--since", help="ISO8601 lower bound (with --recent)")
    pq.set_defaults(func=_cmd_query)

    ps = sub.add_parser("stats", help="store summary")
    ps.set_defaults(func=_cmd_stats)

    args = p.parse_args(argv)
    # subparser args don't inherit top-level defaults automatically for store/config
    args.store = getattr(args, "store", None) or _DEFAULT_STORE
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
