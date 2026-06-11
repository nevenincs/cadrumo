---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-11'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# S454 Filing/Modelo Localization And Error-Hierarchy Audit

## Scope

Audited the S454 filing/modelo/locales surface for residual operator-facing calculation and builder errors that still bypassed the AEAT exception hierarchy or the locale catalogue.

The reviewed source surface was `src/aeat/application/filing`, `src/aeat/application/modelo`, `src/aeat/locales`, and the error registry shard needed for the promoted modelo errors.

## Findings

### S454-001 | MEDIUM | Modelo calculation-input validation still raised bare ValueError

`modelo work calculate` input helpers raised bare `ValueError` for invalid detail rows, decimal override parsing, non-numeric casilla targets, ambiguous or unknown bare casilla numbers, grouped shortcut preconditions, and missing semantic-role casillas.

Status: resolved. These now raise `ModeloCalculateInputError` subclasses derived from `ModeloError` and `ValueError`, carry stable registry entries, structured context, and `application.modelo.errors.*` translation keys.

### S454-002 | LOW | Revision-pick consistency guards bypassed the AEAT hierarchy

`ModeloRevisionPick` rejected internally inconsistent explicit-revision requests with bare `ValueError`.

Status: resolved. The guards now raise `ModeloRevisionPickError`, registered as `REFUSED_MODELO_REVISION_PICK`, with locale-backed messages.

### S454-003 | INFO | Locale catalogue drift discovered in current tree

The locale audit surfaced unrelated ledger invoice key drift from the moved shared tree: code now referenced `cli.app.ledger.invoice.*` while catalogues still carried older collectible/payable invoice leaves.

Status: resolved through `aeat.locales scaffold`. No ledger code was changed in this S454 pass.

### S454-004 | INFO | Residual raw exceptions are outside S454 operator-facing remediation scope

The post-patch scan still reports a Pydantic model validator `ValueError`, an internal profile-binding parse sentinel that is caught and debug-logged, a test helper `RuntimeError`, and a modelo export cleanup `except Exception` that discards temporary output and re-raises.

Status: no S454 action required. No exception-swallowing site was found in the filing/modelo application surface.

### S454-005 | MEDIUM | CLI casilla-normalisation coverage is blocked before S454 code

The explicit entrypoint run for `test_modelo_casilla_normalisation.py` fails during work-unit creation with `Internal. Wizard catalogue has not been registered`, exit code 6. The failure happens before the casilla normalisation or calculation-input path.

Status: external current-tree blocker, not resolved in S454. Lower-level S454 behavior and registry gates passed.

## Verification

Passed:

- `uv run --no-sync python -m aeat.locales audit`
- `uv run --no-sync python -m aeat.locales scaffold --check`
- `uv run --no-sync pytest src/aeat/tests/test_parity.py src/aeat/tests/test_locale_translation_honesty.py src/aeat/tests/test_locale_coverage_hardened_errors.py src/aeat/tests/test_locale_coverage_inventory.py src/aeat/tests/test_locale_tr_positional_inventory.py -q`
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_calculate_input_error_localization.py -q`
- `uv run --no-sync pytest src/aeat/application/tests/test_error_class_registration.py src/aeat/application/tests/test_error_envelope_enrollment.py src/aeat/tests/test_calc_sheets_error_hierarchy.py -q`
- `uv run --no-sync pytest src/aeat/tests/test_no_bare_except.py src/aeat/tests/test_except_clause_narrowing.py -q`
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_work_addressing.py src/aeat/application/modelo/tests/test_actions.py -q`
- `uv run --no-sync ruff check src/aeat/application/modelo/_calculate_input.py src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/tests/test_calculate_input_error_localization.py src/aeat/core/errors/registry/_application_part2.py`

Failed, external to the S454 patch:

- `uv run --no-sync pytest -m "integration or hex_entrypoint" src/aeat/entrypoints/cli/tests/test_modelo_casilla_normalisation.py -q`

The failure is the current-tree wizard catalogue startup registration error described in S454-005.
