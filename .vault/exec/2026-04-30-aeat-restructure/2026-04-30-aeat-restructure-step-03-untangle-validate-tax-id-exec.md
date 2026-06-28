---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-02-phase1-schema-extractor-exec]]"
---

# 2026-04-30-aeat-restructure step-03 untangle validate_spanish_tax_id

## status

Step 3 PR 1 of N — resolves layered violations 4 + 5 in one move (`storage._master_key` NIF canary + `sanitizer._records` synthetic NIF check), per ADR Constraints / Audit-grounded action list and research-doc Layered-architecture violations consolidated.

Historical execution note: the temporary back-compat shim mentioned
below reflects the Step-3 migration state and was later removed by the
hard-cutover continuation.

## scope

- Promote `validate_spanish_tax_id` from `aeat.domain.financial.invoices._validators` (subpackage-private) to public `aeat.adapters.inbound.identity` (Shared Kernel staging — destination per ADR is `core/identity/`, but the old layout has no `core/`; `aeat.adapters.inbound.identity` is the closest cohesive home and Step 7's keystone PR will split `aeat.adapters.inbound.identity` into `core/identity/` (validation) + `adapters/inbound/identity/` (parsing) anyway).
- New module: `src/aeat/adapters/inbound/identity/_tax_id.py` (function + 3 private helpers + 5 algorithm constants).
- Re-export from `aeat/adapters/inbound/identity/__init__.py`.
- `aeat/domain/financial/invoices/_validators.py` becomes a back-compat shim — re-imports `validate_spanish_tax_id` from `aeat.adapters.inbound.identity`. Local definition removed.
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
- Existing `aeat/domain/financial/invoices/test_validators.py` continues to import from `_validators` (re-export shim) and passes.

## findings (FIX / FILE / STRIKE)

None additional — change is the violation untangle itself.

## next step

Step 3 PR 2 — `verification._verify` private-bypass into `formulas._ledger.Discrepancy` + `formulas._ruleset.Ruleset` (audit 19, layered violation #6).
