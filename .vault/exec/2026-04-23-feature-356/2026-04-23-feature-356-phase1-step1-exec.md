---
tags:
  - "#exec"
  - "#feature-356"
date: 2026-04-23
modified: '2026-04-23'
related:
---

# 2026-04-23-feature-356-phase1-step1

## objective

Port 11 files of uncommitted follow-up work from the stale
`feature-253-category-assignment` worktree to a new branch
`feature/356-category-assignment-followup` off main (tip `09e343b`).

## changes delivered

Six commits on `feature/356-category-assignment-followup`:

1. `feat(transactions): add category_id + notes to ClassificationHistoryEntry (#356)`
   - `_models.py`: two new fields with validators on `ClassificationHistoryEntry`
   - `_service.py`: 7-tuple `_EntrySignature`; `snapshot_classification_state`
     propagates the new fields

2. `feat(cli/financial): add 'aeat financial txs build' ingestion command (#356)`
   - `txs.py`: `build_cmd`, `_build_catalogue`, `_build_catalogue_from_ndjson`,
     `_read_ndjson_text` (BOM-aware encoding detection), `_catalogue_from_raw_transactions`,
     `_fallback_provider_for_build`; optional `--as` on classify; `--pct` guard;
     category outgoing-only guard; `category` column in `list_cmd` header

3. `chore(cli): update financial sub-app help text to reflect current scope (#356)`
   - `__init__.py`: help string cites #73, #74, #75

4. `refactor: demote service-layer load/save logs from info to debug (#356)`
   - `invoices/_service.py`: two `.info` → `.debug` calls

5. `test(transactions): extend CLI tests for category_id, notes, and build_cmd (#356)`
   - `test_cli.py`: 11 new test functions covering the schema extension and build_cmd

6. `docs(readme): rewrite Quick-start to show full transaction workflow (#356)`
   - `README.md`: Quick-start now shows `txs build / list / classify`

## key technical decisions

- `_read_ndjson_text` only attempts UTF-16 when a BOM (`\xff\xfe` or `\xfe\xff`)
  is present; UTF-16 decoding never raises `UnicodeDecodeError` and would
  silently mis-interpret CP1252 bytes as paired UTF-16 code units.
- Stale worktree's `save_transactions_fn` injection seam was dropped; main's
  `test_reconciliation.py` uses `monkeypatch.setattr` on `_save_transactions`
  directly, and the seam breaks that patch's module-level interception.
- `test_categories_cli.py` changes from stale worktree were dropped; they
  asserted `label_es` which is not in the `categories list` JSON output.

## test results

256 unit tests pass; ruff check + ruff format clean; ty type check clean.
All pre-commit hooks pass.
