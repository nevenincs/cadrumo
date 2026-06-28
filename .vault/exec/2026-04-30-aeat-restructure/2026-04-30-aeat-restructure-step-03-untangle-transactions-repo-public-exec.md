---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-03-untangle-casillas-cli-tests-exec]]"
---

# 2026-04-30-aeat-restructure step-03 untangle transactions._repository

## status

Step 3 PR 4 of 4 — final substantive untangle for Step 3. Resolves layered violation 3 (audit 5: `filing._review` → `aeat.domain.financial.transactions._repository`) AND 7 ancillary subpackage-private bypasses across `cli/financial/`, `cli/review/`, and `cli/submission/`.

## scope

Promote `TransactionCatalogueRepository` and `ImportSummary` from `aeat.domain.financial.transactions._repository` (subpackage-private) to public `aeat.domain.financial.transactions`. Rewrite 9 caller sites to import from the public surface.

## promoted symbols

- `TransactionCatalogueRepository` — repository class wrapping the encrypted-envelope persistence of the transaction catalogue.
- `ImportSummary` — pydantic frozen model summarising one import operation.

## caller sites rewritten (9)

- `src/aeat/entrypoints/cli/financial/ingest.py` (lines 18, 134)
- `src/aeat/entrypoints/cli/financial/invoices.py` (line 258)
- `src/aeat/entrypoints/cli/financial/_catalogue.py` (line 30)
- `src/aeat/entrypoints/cli/review/test_cli.py` (line 37)
- `src/aeat/entrypoints/cli/review/test_review.py` (line 23)
- `src/aeat/entrypoints/cli/review/test_review_cli.py` (line 21)
- `src/aeat/entrypoints/cli/submission/test_cli.py` (line 21)
- `src/aeat/application/filing/_review.py` (lines 309, 324) — the audit's named violation site

All rewrites: `transactions._repository` → `transactions` in the import path.

## verification

- `python -c "from aeat.domain.financial.transactions import TransactionCatalogueRepository, ImportSummary"` — succeeds.
- `pytest --collect-only`: 6796/6820 tests collect; zero collection errors.
- `grep -rn "financial\\.transactions\\._repository" src/aeat --include="*.py"` — zero hits in production source (only stale `.pyc` bytecode).

## findings (FIX / FILE / STRIKE)

None additional — clean batch promotion + sed rewrite.

## step 3 wrap-up

After this PR merges, Step 3 closes:

| Violation | Resolution PR |
|---|---|
| 1: `casillas` → `aeat.entrypoints.cli` | Step 3 PR 3 (#485 — relocate tests) |
| 2: `profile.assets` + `profile.inventory` → `formulas._rulesets.modelo_100` | Step 3 PR 2 (#484 — formulas-public-surface promotion) |
| 3: `filing._review` → `financial.transactions._repository` | this PR (Step 3 PR 4) |
| 4: `storage._master_key` → `validate_spanish_tax_id` | Step 3 PR 1 (#483 — `aeat.adapters.inbound.identity` promotion) |
| 5: `sanitizer._records` → same as #4 | Step 3 PR 1 (#483 — same resolution as #4) |
| 6: `verification._verify` → `formulas._ledger`/`._ruleset` | Step 3 PR 2 (#484 — public-surface) |
| 7: `cli/filing/__init__.py` → 4-level deep `formulas` privates | Step 3 PR 2 (#484 — public-surface) |

7 violations resolved across 4 PRs (#483, #484, #485, this).

## next step

Step 4 — Tier-2 security-audit prep (HARD GATE before Step 7 layout-move PR can merge). The audit's `resolve_record_json_path` boundary needs an explicit guardrail unit test that survives the move to `core/paths.py` location.
