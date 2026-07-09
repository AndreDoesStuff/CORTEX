"""THALAMUS entrypoint (Deliverable 3).

One command that hits all wired sources and prints the combined, UNRANKED,
UNFILTERED list of normalized records. That is the entire Phase 0 exit criterion.

No persistence, no ranking, no summarization-by-LLM. "Since last time" is modeled
as an explicit --since bound (default: last 7 days) so no state is stored on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .adapters import ADAPTERS, SourceSkipped
from .models import Signal
from .registry import SourceConfig, load_sources
from .secrets import MissingSecret

_DEFAULT_WINDOW_DAYS = 7


def _find_config(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    cwd = Path.cwd() / "sources.json"
    if cwd.exists():
        return cwd
    return Path(__file__).resolve().parent.parent / "sources.json"


def _parse_since(value: str | None, all_time: bool) -> datetime | None:
    if all_time:
        return None
    if value is None:
        return datetime.now(timezone.utc) - timedelta(days=_DEFAULT_WINDOW_DAYS)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        sys.exit(f"error: --since must be ISO8601 (e.g. 2026-07-01T00:00:00Z), got {value!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _cred_status(src: SourceConfig) -> str:
    """Cheap check (no network) of whether referenced secrets are present."""
    import os

    missing = [
        v[len("env:"):]
        for v in src.auth.values()
        if isinstance(v, str) and v.startswith("env:") and not os.environ.get(v[len("env:"):])
    ]
    return "ok" if not missing else f"missing {', '.join(missing)}"


def _list_sources(sources: list[SourceConfig]) -> None:
    print("Registered sources:\n")
    for s in sources:
        flag = "on " if s.enabled else "off"
        print(f"  [{flag}] {s.id:<18} type={s.type:<8} trust={s.trust_level:<6} "
              f"creds={_cred_status(s)}")
        print(f"        scope: {s.scope}")
    print()


def _emit(signals: list[Signal], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps([s.to_dict() for s in signals], indent=2, ensure_ascii=False))
        return
    # text
    by_source: dict[str, list[Signal]] = {}
    for s in signals:
        by_source.setdefault(s.source_id, []).append(s)
    for source_id, items in by_source.items():
        print(f"\n=== {source_id} ({len(items)}) ===")
        for s in items:
            print(f"  · [{s.category}] {s.summary}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cortex",
        description="THALAMUS — poll wired sources, print combined normalized signal (Phase 0).",
    )
    parser.add_argument("--config", help="path to sources.json (default: ./sources.json)")
    parser.add_argument("--since", help="ISO8601 lower bound (default: last 7 days)")
    parser.add_argument("--all", action="store_true", help="ignore --since; fetch all recent")
    parser.add_argument("--source", help="only run this source id")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--list-sources", action="store_true",
                        help="list registered sources + cred status, no network")
    args = parser.parse_args(argv)

    load_dotenv()  # pull secrets from .env into the environment

    config_path = _find_config(args.config)
    if not config_path.exists():
        sys.exit(f"error: source registry not found at {config_path}")
    sources = load_sources(config_path)

    if args.list_sources:
        _list_sources(sources)
        return 0

    since = _parse_since(args.since, args.all)
    window = "all recent" if since is None else f"since {since.isoformat()}"
    print(f"THALAMUS · {window} · registry {config_path}", file=sys.stderr)

    all_signals: list[Signal] = []
    skipped: list[str] = []
    errored: list[str] = []

    with httpx.Client(timeout=30.0) as client:
        for src in sources:
            if args.source and src.id != args.source:
                continue
            if not src.enabled:
                skipped.append(f"{src.id} (disabled)")
                continue
            adapter_cls = ADAPTERS.get(src.type)
            if adapter_cls is None:
                errored.append(f"{src.id} (no adapter for type {src.type!r})")
                continue
            try:
                signals = adapter_cls(src).fetch(since, client)
                all_signals.extend(signals)
            except (SourceSkipped, MissingSecret) as e:
                skipped.append(f"{src.id} ({e})")
            except httpx.HTTPStatusError as e:
                errored.append(f"{src.id} (HTTP {e.response.status_code})")
            except httpx.HTTPError as e:
                errored.append(f"{src.id} ({e})")

    _emit(all_signals, args.format)

    print(f"\n{len(all_signals)} records from "
          f"{len({s.source_id for s in all_signals})} live source(s).", file=sys.stderr)
    if skipped:
        print(f"skipped: {'; '.join(skipped)}", file=sys.stderr)
    if errored:
        print(f"errors:  {'; '.join(errored)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
