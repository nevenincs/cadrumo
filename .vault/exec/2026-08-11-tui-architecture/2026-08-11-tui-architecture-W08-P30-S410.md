---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:08919e2b5ed044814ad681873e665770661624e7cf92e659864a634b1a557918'
step_id: 'S410'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Extend the capture-coherence guard to everything the generation door now reads. It re-reads and compares the profile record, work units, calculation revisions and filing records, which was the whole read set when it was written; the door now also reads transactions, invoices and bucket events for Ledger and projects every work unit for Modelo. A write landing mid-capture yields a generation whose Ledger snapshot is from a different instant than its Declarations, and nothing detects it.

## Scope

- `src/cadrumo/application/workbench_generation.py`

## Changes

- `M` `src/cadrumo/application/workbench_generation.py`
- `M` `src/cadrumo/application/ledger/workspace_reader.py`
- `M` `src/cadrumo/application/ledger/actions_manual.py`
- `M` `src/cadrumo/application/tests/test_workbench_generation.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/tests/test_workbench_generation.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`

## Notes

The ledger stores expose no revision handle, so the guard compares the catalogues
themselves across the two reads. Bucket events stay outside it: they supply review
context only and have no whole-catalogue read to compare.

Detector proven non-vacuous by deleting the one comparison, which turns the refusal test
into DID NOT RAISE.

`summarize_manual_transactions` resolved a concrete repository before doing any work, so
it rejected every protocol implementation and made the ledger read path unreachable
without real encrypted persistence. Resolution is now lazy and happens only where a read
or a period-scoped preflight needs it.

Twelve ledger and six overview failures observed in the surrounding suites are
PRE-EXISTING and not caused by this change: the same six overview failures reproduce with
this file reverted to its prior committed revision, checked by copy rather than by any
destructive git operation.
