---
tags:
  - '#reference'
  - '#sync-control-surface'
date: '2026-08-08'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:dcdd199585becf805af6712deb1bff05b6a10c55a87f3b9f4d798e8f12aed762'
related:
  - '[[2026-08-08-sync-control-surface-adr]]'
---

# `sync-control-surface` reference: `grounding`

## Summary

Codebase grounding for the decision on the shape of sync controls across the
Google Sheets calculation export and the AEAT filed-history sweep.

## Google Sheets calculation sync

The write mechanics are a batch clear over every managed tab range followed by a batch update — a destructive whole-surface overwrite, not a merge. Protected ranges are deleted and re-created. Foreign content is refused rather than adopted.

What does not exist for this surface: no dry-run or preview on `export`; no scope narrower than modelo, period and year; no progress; no cancellation.

Last-sync marking exists only inside the remote artefact: a managed
developer-metadata key set written by the adapter, carrying engine version,
registry hash, modelo, revision, year, period and an export instant. The pull
path in `_calc_sheets_pull.py` reads those keys back and deliberately EXCLUDES
the export instant from the staleness match, describing it as informational.
Nothing is recorded locally.

## AEAT filed-history sweep

The CLI entry is `aeat app live filed pull-all` in `src/cadrumo/entrypoints/cli/_app_live.py`, whose only options are an output root and a result limit. Its siblings are `filed discover`, `filed pull` (which does carry modelo and year scope) and `filed pull-sources`.

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

A preview `Notice` carries the apply command as its suggestion. Three divergence notice classes are rendered: value disagreement, withheld or redacted values, and operator-cleared paths.

## Last-sync provenance across the tree

A search for last-synced, synced-at, last-pull and last-run naming across `src/` and `.vault/` returns nothing. No surface records that a sync ran.

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
