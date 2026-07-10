# CORTEX

A personal agent fleet, built in phases named after brain regions. Each phase
has a hard exit criterion before the next begins. Three are built so far:

| Phase | Region | Command | What it does |
|---|---|---|---|
| 0 | **THALAMUS** | `cortex` | Intake — polls sources on demand, normalizes to one shape. Read-only. |
| 1 | **HIPPOCAMPUS** | `hippocampus` | Memory — append-only, immutable grounded log of what THALAMUS pulled. |
| 2a | **BROCA** | `broca` | Conversation — ask what's going on, get a confidence-graded spoken answer. |

Everything is **read-only against its sources**, carries **provenance** end to end,
and does **no ranking, no task management, and no writes** — those are later phases.

The data flows one direction: **THALAMUS → HIPPOCAMPUS → BROCA.**

```
cortex … --format json  >  snapshot.json      # 1. pull + normalize
hippocampus ingest --snapshot snapshot.json    # 2. append into memory
broca "what's open on AXON right now?"          # 3. ask the memory, spoken answer
```

---

## Setup

```bash
cd ~/Desktop/CORETEX/cortex
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

cp .env.example .env      # then paste in your tokens (.env is git-ignored)
```

Installs three console scripts: `cortex`, `hippocampus`, `broca`. (Each also runs
as `python -m cortex`, `python -m cortex.hippocampus.cli`, `python -m cortex.broca.cli`.)

Tokens (only THALAMUS needs credentials; HIPPOCAMPUS and BROCA read local state):
- **Jira**: `JIRA_EMAIL` + `JIRA_API_TOKEN` — https://id.atlassian.com/manage-profile/security/api-tokens
- **Figma**: `FIGMA_TOKEN` (file read scope) — https://www.figma.com/developers/api#access-tokens
- **GitHub**: `GITHUB_TOKEN` — required because `AndreDoesStuff/CORTEX` is private. Fine-grained PAT with read (Contents + Issues). Public repos work without a token.

Python 3.9+ (kept 3.9-safe for the system interpreter). Dependencies: `httpx`, `python-dotenv`. BROCA's voice uses the macOS built-in `say` (no dependency; degrades to text-only elsewhere).

---

## THALAMUS — `cortex`

Polls every enabled source and prints the combined, **unranked, unfiltered** list
of normalized records. No persistence — "what's new since last time" is an explicit
`--since` bound, not stored state.

```bash
cortex --list-sources          # registry + which creds are present (no network)
cortex                         # combined signal, last 7 days, text
cortex --since 2026-07-01      # explicit ISO8601 lower bound
cortex --all                   # ignore --since; everything recent
cortex --format json           # machine-readable (pipe this into hippocampus)
cortex --source figma-axon-main # one source only
```

A source with missing creds or an API error is reported and skipped — it never
kills the combined run.

**Wired sources** (edit [`sources.json`](sources.json) to change; secrets are referenced by
name, never inlined):

| Source | Domain | Signal |
|---|---|---|
| `jira-axon` | `axon` | AXON tickets (Jira project `UX`), read-only |
| `figma-axon-main` | `axon` | version activity, main branch |
| `figma-axon-table` | `axon` | version activity, table branch |
| `github-cortex` | `cortex-self` | `AndreDoesStuff/CORTEX` commits + issues/PRs |

Add more repos: append `"owner/repo"` strings to `github-cortex.config.repos`.

**Normalized record** (every source emits this shape):

```json
{
  "source_id": "jira-axon",
  "fetched_at": "2026-07-09T12:00:00+00:00",
  "category": "job | idea | trend | fyi",
  "raw": { "...": "untouched original payload — provenance anchor" },
  "summary": "one factual line, no inference beyond what's in raw"
}
```

`raw` is mandatory and never dropped.

---

## HIPPOCAMPUS — `hippocampus`

An **append-only, immutable** memory log (JSONL). It never edits or deletes a
record — a ticket closing is a *new* appended fact, not a mutation. Re-ingesting
the same pull is idempotent (dedup by `memory_id`).

Global flags come **before** the subcommand: `--store PATH` (default
`hippocampus_memory.jsonl`, or `$HIPPOCAMPUS_STORE`) and `--config sources.json`.

```bash
# Ingest — from a saved THALAMUS snapshot, or live
hippocampus ingest --snapshot snapshot-2026-07-09.json
hippocampus ingest --live --since 2026-06-09T00:00:00Z

# Query — grounded, cited answers
hippocampus query --open --domain axon                       # live work, by lifecycle_state
hippocampus query --recent --source figma-axon-table         # recent activity, one source
hippocampus query --recent --domain axon --since 2026-06-30  # recent activity, a domain
hippocampus stats                                            # counts by source/lifecycle/batch

# Point at a specific store:
hippocampus --store /path/to/memory.jsonl query --open --domain axon
```

**Memory record** adds grounding fields on top of the THALAMUS shape:

```json
{
  "memory_id": "<hash of source_id + entity + occurred_at>",
  "source_id": "jira-axon",
  "occurred_at": "<the event's OWN timestamp from raw, not fetch time>",
  "fetched_at": "<when THALAMUS pulled it>",
  "signal_category": "job | idea | trend | fyi",
  "lifecycle_state": "open | closed | obsolete | n/a",
  "batch_id": "<null, or shared id for one real-world batch event>",
  "raw": { "...": "untouched" },
  "summary": "naive, factual"
}
```

- `lifecycle_state` comes from **explicit source fields only** (Jira `statusCategory`
  + `resolution`; GitHub issue state), never inferred from title text.
- `batch_id` collapses one real-world batch event (e.g. a bulk close of 39 tickets)
  in display without dropping any record — each keeps its own `raw`.
- **Domain** is joined from `sources.json` at query time, not stored per record.

---

## BROCA — `broca` (Phase 2a: text-in, voice-out)

Ask what's going on and get a **confidence-graded** answer, spoken aloud on macOS.
Reactive and read-only — it relays HIPPOCAMPUS memory, nothing more. It reuses
HIPPOCAMPUS's query interface; it does not query sources directly.

```bash
broca "what's open on AXON right now?"    # ask once, speak the answer
broca                                     # interactive session
broca --no-voice "what's up with AXON?"   # print only, don't speak
broca --trace "what's open on AXON?"      # show narration source (llm / fallback)
broca --voice-file out.aiff "..."         # write audio to a file (say only; testing)
```

In an interactive session, say **"details"** (or "tell me more") to expand the
previous answer with full citations. Context is held **within the session only** —
never carried across runs. `exit` / `quit` / Ctrl-D to leave.

**Every answer lands in exactly one shape — never blended.** Confidence is carried
in the words (voice has no badge):

| Shape | Example | Meaning |
|---|---|---|
| **grounded** | "11 open on AXON right now. Want them listed?" | cites specific memories (`memory_id` + provenance) |
| **inferred** | "Looks like most got cleared out — 39 closed, 11 open — but that's me reading the counts." | interpretation over grounded data, flagged as such |
| **unknown** | "I don't have anything on that yet." | no data — said flat, once, no padding |
| **partial** | "I've got version history — but nothing on comments; I don't pull those yet." | a real capability gap stated plainly |
| **scope** | "That's prioritization — I don't do that yet." | a capability boundary, not a false data gap |
| **conversational** | "Alive's a stretch — well-organized, maybe." | small talk / questions about CORTEX itself; makes no data claim |

**How it phrases and speaks — two graceful-degradation layers:**

1. **Narrator** (`cortex/broca/narrator.py`): the final line is phrased by
   `claude-haiku-4-5` (only if `ANTHROPIC_API_KEY` is set) from a closed *fact
   packet*. Output is validated token-by-token — every number/date/ticket-ID must
   exist in the packet — and any mismatch or API failure falls back to a
   deterministic phrasing template. The LLM can never introduce an unstated fact.
2. **Voice** (`cortex/broca/voice.py`): audio is rendered by **Voicebox** — a
   local, on-device voice-cloning server (no key, no cost, nothing leaves the
   machine) — using the `VOICEBOX_PROFILE_NAME` profile: generate → poll →
   fetch → play. On any failure or timeout it falls back to `say -v Samantha`.

Both layers never surface a raw error and never leave dead air. Speech **input**
(STT) is Phase 2b.

---

## Layout

```
sources.json            # source registry (domains + secret references, no inline secrets)
cortex/
  cli.py  models.py     # THALAMUS: entrypoint + normalized Signal shape
  registry.py secrets.py
  adapters/             # one read-only adapter per source type (jira, figma, github)
  hippocampus/
    record.py store.py  # append-only memory record + JSONL log
    ingest.py extract.py batch.py  # signal->record, explicit-field lifecycle, batch clustering
    query.py cli.py     # grounded cited queries + `hippocampus` CLI
  broca/
    intent.py respond.py  # question -> query routing + answer shaping
    voice.py answers.py cli.py   # macOS say, shaped-answer types, `broca` CLI
```

Runtime state — the memory log (`*.jsonl`), THALAMUS snapshots, and `.env` — is
git-ignored. It contains raw source payloads and must not be committed.

## Principle

No claim CORTEX surfaces is ungrounded. Every "here's what's happening" traces to
a source and a timestamp, or it's explicitly labeled as inference. Jira is
read-only awareness for AXON — permanently, at every phase.
