---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S153'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P21.S153 CLI boundary mitigation closure evidence

Scope:
- W06.P18 through W06.P21
- `src/aeat/entrypoints/cli`
- `src/aeat/application/modelo`

## Description

- Consolidate W06 closure evidence.
- Record residual monolith and boundary risks explicitly.
- Confirm plan and test gates after W06.P20 decomposition and W06.P21 closure audits.

## Outcome

- W06.P20 is closed: command-group split, support helper extraction, architecture guard, size guard, and regression coverage are complete.
- W06.P21 is closed: exact audit, semantic audit, static gates, focused regression tests, and residual matrix are persisted.
- Plan validation passes with one existing warning about non-monotonic step identifiers.

## Residual Risk Matrix

| Risk | Current control | Residual action |
| --- | --- | --- |
| `_modelo.py` remains large | `_modelo.py` has a frozen size budget and extracted modules cannot import it | Continue extracting lifecycle, calculation, revision, filing-record, verification-report, audit, and reconciliation groups |
| `_ledger.py`, `_app_live.py`, `_config/__init__.py` remain large | Static module-size guard freezes current budgets | Add future waves to split those modules under the same budget test |
| Extracted CLI module imports private domain exception types | Architecture guard tracks explicit exception rows | Move exception translation behind application facades when those service APIs exist |
| `work_calculate` remains overgrown | Static command-size guard freezes current budget | Split work calculation command body after work-input helpers are relocated |
| Some exact selector helpers remain in `_modelo.py` | RAG and exact audits identify `_resolve_revision_for_cli` as legacy residual | Move work addressing helpers to a dedicated support module in the next extraction slice |
| Legacy registry authority reads remain in `_modelo.py` | Exact audit identifies `resources().modelos.authority` reads; static guards prevent extracted modules from adding private application bypasses | Move registry query/introspection construction behind application facades in a follow-up slice |

## Notes

- W06 did not make every CLI module small. It installed enforced budgets and extracted several modelo command/support surfaces so remaining debt cannot grow silently.
- `_modelo.py` currently remains a legacy root around 4.2k lines with `work_calculate` frozen at its current long Typer signature/body budget.

Verification:
- `uv run --no-sync vaultspec-core vault plan status .vault/plan/2026-06-04-modelo-addressing-ux-plan.md` - 85 of 85 complete.
- Static W06 gates - 5 passed.
- Focused application regression lane - 66 passed.
- Focused CLI regression lane - 100 passed.

## 2026-06-04 Rerun Evidence

- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-modelo-addressing-ux-plan.md` - passed with existing PLAN022 warning.
- `uv run --no-sync pytest -m docs src/aeat/entrypoints/cli/test_doc_reference_drift.py src/aeat/entrypoints/cli/test_doc_reference_conformance.py -q` - 8 passed.
- `uv run --no-sync ruff check <explicit modelo-addressing application/CLI surface>` - passed.
- `uv run --no-sync pytest -x <explicit modelo-addressing application/CLI regression surface>` - 85 passed.
- `uv run --no-sync vaultspec-core vault check all --feature modelo-addressing-ux` - failed on the known vault structure filename convention violations for existing step records; no repair was run.
