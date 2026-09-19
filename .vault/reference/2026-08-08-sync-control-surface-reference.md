---
tags:
  - '#reference'
  - '#sync-control-surface'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b08b0ac0eae832d52ee71951e98d8d3acdb4ed289c7ac07fa7bbf137d0817f00'
related:
  - '[[2026-08-08-sync-control-surface-adr]]'
---

# `sync-control-surface` reference: `grounding`

## Summary

Codebase grounding for the decision on the shape of sync controls across the
Google Sheets calculation export and the AEAT filed-history sweep.

## Google Sheets calculation sync

CLI verbs live in `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`:
`export` writes to Drive and Sheets; `verify` also creates a spreadsheet and
writes cells under the same export capability; `pull` is read-back only;
`compute` persists nothing and refuses on stale metadata.

The pure plan is built in
`src/cadrumo/application/storage/calc_sheets/_engine.py` by `build_export_plan`,
which stamps an export instant onto `SheetExportMetadata` in the sibling
`_records.py`.

The adapter is `src/cadrumo/adapters/outbound/google/_calc_sheets_apply.py`.
`apply_export_plan` documents idempotence at the spreadsheet level: applying the
same plan twice updates the same spreadsheet rather than creating a duplicate,
provided the per-period subfolder and spreadsheet title stay stable. The write
mechanics are a batch clear over every managed tab range followed by a batch
update — a destructive whole-surface overwrite, not a merge. Protected ranges
are deleted and re-created. Foreign content is refused rather than adopted.

What does not exist for this surface: no dry-run or preview on `export`; no
scope narrower than modelo, period and year; no progress; no cancellation. A
three-way local/Sheets/AEAT parity report DOES exist, built by
`verify_modelo_parity` in
`src/cadrumo/application/storage/calc_sheets/_parity_harness.py` and rendered as
typed divergence rows — but it is attached to `verify`, not to `export`.

Last-sync marking exists only inside the remote artefact: a managed
developer-metadata key set written by the adapter, carrying engine version,
registry hash, modelo, revision, year, period and an export instant. The pull
path in `_calc_sheets_pull.py` reads those keys back and deliberately EXCLUDES
the export instant from the staleness match, describing it as informational.
Nothing is recorded locally.

## AEAT filed-history sweep

The CLI entry is `aeat app live filed pull-all` in
`src/cadrumo/entrypoints/cli/_app_live.py`, whose only options are an output
root and a result limit. Its siblings are `filed discover`, `filed pull` (which
does carry modelo and year scope) and `filed pull-sources`. The TUI manager
reaches the same action through
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py`.

The application layer is
`src/cadrumo/application/live/_filed_data_capture.py`. `pull_filed_history`
sequences discovery, bulk capture, the IVA wallet and notificaciones, collecting
per-stage failures. Observations persist through
`FiledDeclaracionObservationStore` in
`src/cadrumo/adapters/outbound/aeat/sede/_observation_store.py`, content-
addressed by SHA-256.

**The sweep is not append-only.** The capture module states that a re-capture is
an unconditional upsert; observations are keyed on modelo, ejercicio, period and
expediente and are replaced.

The module already computes the divergence a re-capture would introduce —
`casillas_a_recapture_would_change` — and surfaces it through
`recapture_divergence_notices` under the `live.filed.pull_all.recapture_divergence`
code, together with expected-but-not-found and found-more-than-expected notices.
The diff is computed AFTER the upsert has landed.

What does not exist: no dry-run flag; no scope on `pull-all` beyond the limit;
no progress (the progress context in the module is timeout-diagnostic payload,
not live reporting); no cancellation beyond per-query timeouts. Provenance is a
per-observation capture instant used for ordering; there is no sweep-level
record.

## The censo cotejo precedent

`src/cadrumo/entrypoints/cli/_config/_censo_file.py` implements preview by
default with `--apply` as the commit door on both `censo file` and `censo pull`;
the commit branch is the only branch that writes, and preview renders the same
rows. A preview `Notice` carries the apply command as its suggestion. Three
divergence notice classes are rendered: value disagreement, withheld or redacted
values, and operator-cleared paths.

The single apply authority is `apply_cotejo` in
`src/cadrumo/application/user_profile/_cotejo_apply.py` — atomic clearing plus
adopted plus fresh divergence rows through one write, then exactly one
`CENSO_APPLIED` event. The typed row is `CensoDivergence`; the namespace is
`censo.divergencia` with indexed subpaths; the standing warning is
`censo_divergence_notice`, emitted on profile read from
`src/cadrumo/entrypoints/cli/_config/_profile_inspect.py`.

## Last-sync provenance across the tree

A search for last-synced, synced-at, last-pull and last-run naming across `src/`
and `.vault/` returns nothing. What exists is per-record ingest stamps only: a
capture instant per filed observation; an ingest instant on ledger raw
provenance in `src/cadrumo/adapters/inbound/financial/providers/_base.py`; export
instants on modelo and filing export records; an export instant on the portable
profile bundle. No surface records that a sync ran.

## Prior decisions bearing on preview and dry-run

`2026-04-30-inventory-management-cli-design-adr` requires preview/apply
semantics on mutating commands whose calculation, migration or overwrite effects
need review, and forbids silent overwrite of duplicate identifiers.

`2026-05-14-cli-workflow-redesign-list-vs-query-leaf-semantics-adr` permits a
sibling preview leaf where operators need a what-would-be-exported view, leaving
the per-surface choice to implementation.

`2026-04-12-workflow-engine-adr` and `2026-04-16-submission-safety-sweep-adr`
make dry-run the default for live submission specifically, with double
confirmation to go live — a stricter regime than either sync surface, and
scoped to remote mutation of AEAT.

The ledger removal, ledger lifecycle, borrador snapshot and config-repair
records each spell the preview as a `--dry-run` flag on the mutating verb.

`2026-07-25-censal-profile-autofill-adr` fixes `apply_cotejo` as the single
apply authority emitting one event; the preview-by-default shape is stated in
code rather than in that record's decision text.

No record in the corpus rules on sync provenance.
