---
tags:
  - "#audit"
  - "#profile-lifecycle-cli"
date: "2026-05-17"
related:
  - "[[2026-05-16-profile-lifecycle-cli-adr]]"
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
  - "[[2026-05-14-profile-bucket-lifecycle-adr]]"
---

# `profile-lifecycle-cli` audit: per-bucket SQLite cascade scope

Inventory + decision record for the unexecuted P02.S20 (per-bucket
SQLite URL through the engine factory) and the architectural
chicken-and-egg blocker the audit surfaced.

## Caller inventory

A haiku discovery pass classified 100 callsites of
`create_engine_from_settings(settings)` across 61 files:

- **Production callers: zero**. Production goes through the
  process-wide singleton `get_engine(settings)` at
  `adapters/persistence/storage/sql/engine.py:132`, which itself
  reads `settings.aeat_database_url`. Only three production
  reads of the settings field exist (`engine.py:118`, `:185`,
  `core/i18n/_render.py:105`).
- **Test isolated-DB fixtures: 98 callsites across 59 test
  files**. Every test that builds an isolated `tmp_path` SQLite
  for roundtrip / persistence coverage. None of them care about
  bucket dimension; they pass an explicit `aeat_database_url`.
- **Engine-factory tests: 2 callsites** in
  `adapters/persistence/storage/sql/_test_engine.py` covering
  URL parsing and parent-dir-creation semantics. These stay
  unchanged.

## Chicken-and-egg blocker

The May-14 profile-bucket-lifecycle ADR mandates that the engine
resolves the database URL from the active bucket's directory
(`<aeat-root>/buckets/<id>/db/aeat.db`). The mandate has a
boot-order problem:

The active-bucket resolution chain reads the plaintext
`<aeat-root>/active-profile` pointer file. Before the operator
runs `aeat config init`, no pointer exists. The engine then has
no URL to construct, so the **WorkflowState load that decides
which init flow to run** cannot complete; the workflow-state row
itself currently lives in the shared SQLite that the engine
would need to read in order to know which bucket to point at.

Two architectural answers exist; the codebase ships neither
today:

1. **WorkflowState moves into the bucket's own database**. The
   global secure-object table goes away; every bucket carries
   its own SQLite. The very first `aeat config init` invocation
   has no engine to open — it provisions the bucket directory
   tree on the filesystem ONLY, then opens the new engine. The
   chicken comes first.

2. **A bootstrap engine path exists at a known root**. The
   global SQLite under `<aeat-root>/state.db` holds only the
   active-profile pointer + the `WorkflowState`. Per-bucket
   SQLite under `<aeat-root>/buckets/<id>/db/` holds the
   encrypted secure-object rows for that profile's facts and
   filings. Two engines, two URL resolution paths.

The May-14 ADR's section 2 reads as option 1. The current
codebase is closer to option 2 in shape (a shared `workflow_state`
secure-object row), but does not separate the engines.

## Scope for landing P02.S20 / S21 honestly

Honest landing requires:

- A design decision between option 1 and option 2 (the May-14
  ADR text leans option 1; the current code is closer to option
  2).
- For option 1: the workflow-state repository moves into the
  bucket's namespace. `register_active_profile` provisions the
  bucket's engine on first call. Migration of the active-profile
  pointer file write to happen BEFORE any engine open.
- For option 2: a typed second URL on `Settings`
  (`aeat_state_database_url`?) for the global state engine, and
  the per-bucket engine resolved separately. `get_engine()`
  becomes `get_state_engine()` + `get_bucket_engine()`.

Either path is single-cut across the whole secure-objects
surface. The user mandate forbids a parallel transitional shim;
the landing happens in one commit covering all production reads
and the `aeat_database_url` Settings field semantics, with the
test surface adapting wholesale to the chosen design.

## Recommendation

Bring this finding to the next architectural-decision pass. The
ADR text supports option 1; the implementation cost is real but
bounded. The two-engine option 2 is less invasive but
contradicts the May-14 mandate.

## P03 cascade has an analogous blocker

P03.S27 (rewire `_resolve_master_key` through `BucketSession`)
has the same root: the crypto path needs to know which session
to read from, and sessions don't exist before unlock. The
operator-facing answer ("unlock the bucket, run verbs inside the
session") requires every secure-objects read to thread a session
reference. That cascades through hundreds of call sites.

The current ClassVar caches in `KeyringMasterKeyProvider` and
`FileFallbackMasterKeyProvider` exist BECAUSE the crypto path
historically did not thread a session. Removing them in favour
of a session-scoped registry replaces one process-global cache
with another; replacing them with caller-threaded sessions is
the architectural answer P03 demands.

P03 is a fresh-session landing too.
