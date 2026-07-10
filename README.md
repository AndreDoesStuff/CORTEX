# CORTEX — THALAMUS (Phase 0)

Intake-and-routing only. Polls André's real sources on demand and normalizes
every signal into one shape — **unranked, unfiltered, read-only, no persistence.**

> Scope guardrail: no memory store (that's HIPPOCAMPUS, Phase 1), no ranking
> (PREFRONTAL, Phase 3), no LLM summaries, **no writes to any source — ever.**
> Jira is read-only awareness for the AXON board, permanently.

## What's wired

| Source | Status | Signal |
|---|---|---|
| `jira-axon` | **live** | AXON issues updated in window (`category: job`) — read-only |
| `figma-axon-main` | **live** | version activity on the main branch (`category: fyi`) |
| `figma-axon-table` | **live** | version activity on the table branch (`category: fyi`) |
| `github-cortex` | **live** | `AndreDoesStuff/CORTEX` commits + issues/PRs (`category: job`) — private repo, needs `GITHUB_TOKEN` |

## Setup

```bash
cd ~/Desktop/CORETEX/cortex
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

cp .env.example .env      # then paste in your tokens (.env is git-ignored)
```

Tokens needed for the live sources:
- **Jira**: `JIRA_EMAIL` + `JIRA_API_TOKEN` — https://id.atlassian.com/manage-profile/security/api-tokens
- **Figma**: `FIGMA_TOKEN` (file read scope) — https://www.figma.com/developers/api#access-tokens
- **GitHub**: `GITHUB_TOKEN` — required because `AndreDoesStuff/CORTEX` is private. Fine-grained PAT with read (Contents + Issues) on that repo. Public repos would work without a token.

## Run

```bash
cortex --list-sources        # show registry + which creds are present (no network)
cortex                       # combined signal, last 7 days, text
cortex --since 2026-07-01    # explicit lower bound
cortex --all --format json   # everything recent, machine-readable
cortex --source figma-axon-main
```

`cortex` == `python -m cortex`. A source with missing creds or an API error is
reported and skipped — it never kills the combined run.

## The normalized shape (every record)

```json
{
  "source_id": "jira-axon",
  "fetched_at": "2026-07-09T12:00:00+00:00",
  "category": "job | idea | trend | fyi",
  "raw": { "...": "untouched original payload — provenance anchor for Phase 1" },
  "summary": "one factual line, no inference beyond what's in raw"
}
```

`raw` is mandatory on every record and is never dropped.

## Adding more sources

Edit [`sources.json`](sources.json):
- **GitHub**: add more `"owner/repo"` strings to `github-cortex.config.repos` to watch additional repos.

## Layout

```
sources.json          # Deliverable 1 — source registry (secrets by reference only)
cortex/models.py      # Deliverable 2 — the one Signal shape
cortex/cli.py         # Deliverable 3 — single entrypoint
cortex/registry.py    # loads sources.json
cortex/secrets.py     # env: reference resolution (no inline secrets)
cortex/adapters/      # one file per source type, all read-only
```

## Handback

Once this returns live data, bring raw output back to Claude Design before
starting HIPPOCAMPUS — the Phase 1 memory schema is designed against what the
adapters actually produce, not the spec in the abstract.
