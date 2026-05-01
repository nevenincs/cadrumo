---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-02-phase1-schema-extractor-exec]]"
---

# 2026-04-30-aeat-restructure step-03 untangle validate_spanish_tax_id

## status

Step 3 PR 1 of N — resolves layered violations 4 + 5 in one move (`storage._master_key` NIF canary + `sanitizer._records` synthetic NIF check), per ADR Constraints / Audit-grounded action list and research-doc Layered-architecture violations consolidated.

## scope

- Promote `validate_spanish_tax_id` from `aeat.domain.financial.invoices._validators` (subpackage-private) to public `aeat.adapters.inbound.identity` as a staging path. The delivered hard-cut layout places the validation algorithm in `aeat.core.identity`; `aeat.adapters.inbound.identity` imports that canonical implementation for inbound parsing callers.
- New module: `src/aeat/adapters/inbound/identity/_tax_id.py` (function + 3 private helpers + 5 algorithm constants).
- Re-export from `aeat/adapters/inbound/identity/__init__.py`.
- `aeat/domain/financial/invoices/_validators.py` temporarily re-imported `validate_spanish_tax_id` during the untangle. The delivered path is `aeat/domain/invoices/_validators.py` importing from `aeat.core.identity`; the old financial package path is not retained.
- 4 caller sites updated to import from `aeat.adapters.inbound.identity` (the public path):
  - `src/aeat/entrypoints/cli/submission/check_nif.py`
  - `src/aeat/entrypoints/cli/submission/export.py`
  - `src/aeat/adapters/persistence/storage/_master_key.py`
  - `src/aeat/adapters/inbound/sanitizer/_records.py`

## pre-untangle violation evidence

Subpackage-private bypass imports (4 sites):

```
src/aeat/entrypoints/cli/submission/check_nif.py:26: from ...financial.invoices._validators import validate_spanish_tax_id
src/aeat/entrypoints/cli/submission/export.py:33: from ...financial.invoices._validators import validate_spanish_tax_id
src/aeat/adapters/persistence/storage/_master_key.py:907: from ..financial.invoices._validators import validate_spanish_tax_id
src/aeat/adapters/inbound/sanitizer/_records.py:18: from ..financial.invoices._validators import validate_spanish_tax_id
```

All 4 reach into `_validators` (leading-underscore subpackage-private module) of an unrelated subpackage (`financial/invoices/`). After untangle: every caller imports from the public surface `aeat.adapters.inbound.identity`.

## post-untangle verification

- `python -c "from aeat.adapters.inbound.identity import validate_spanish_tax_id; print(validate_spanish_tax_id('B12345674'))"` → `B12345674`.
- `pytest --collect-only`: 6796/6820 tests collected (24 deselected). Zero collection errors. (Pre-untangle was 6783/6807 after Step 2 PR 1; the increase is unrelated newly-landed tests.)
- `grep -rn "from \.\\.financial\.invoices\._validators\|from \.\.\\.financial\.invoices\._validators" src/aeat`: zero hits in production source.
- Existing invoice validator tests continue to import from the colocated `_validators` module and pass; in the delivered layout that module imports `validate_spanish_tax_id` from `aeat.core.identity`.

## findings (FIX / FILE / STRIKE)

None additional — change is the violation untangle itself.

## next step

Step 3 PR 2 — `verification._verify` private-bypass into `formulas._ledger.Discrepancy` + `formulas._ruleset.Ruleset` (audit 19, layered violation #6).
