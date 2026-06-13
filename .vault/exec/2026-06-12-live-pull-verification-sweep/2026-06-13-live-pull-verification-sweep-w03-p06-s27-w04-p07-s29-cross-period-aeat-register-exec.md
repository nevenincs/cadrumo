---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S27,S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
---

# W03.P06.S27 / W04.P07.S29 cross-period AEAT register reference

## Scope

Hardened cross-period clean-state evidence so an observation stamped as an
official AEAT source must carry an AEAT register reference, not only `ALTA`
status and authenticated identity.

## Description

- Updated `_aeat_register_provenance_blockers` to require
  `aeat_expediente_id` whenever the calculation observation source kind is one
  of the official AEAT families.
- Added regression coverage for an official Modelo 303 source observation that
  has `ALTA`, an authenticated identity, and a justificante CSV, but no AEAT
  register/expediente reference; it now blocks with
  `mismatched_external_evidence_record`.
- Updated Modelo clean-state fixtures that intentionally model valid AEAT
  filed-history observations to carry both `aeat_expediente_id` and
  `aeat_justificante_csv`.

## Verification

- `vaultspec-rag -t . search --timeout 300 "cross period clean state justificante evidence reference AEAT filed state Modelo filing record blockers"`
  - result: returned the existing cross-period filed-history reference locking
    exec/audit material and the live-pull plan.
- `uv run ruff check src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`
  - result: passed.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py -q --tb=short`
  - result: 13 passed.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q --tb=short`
  - result: 34 passed.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q --tb=short`
  - result: 47 passed.
- `uv run pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py::test_export_modelo_390_passes_clean_state_with_imported_bound_justificantes src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py::test_verify_modelo_390_refuses_csv_register_prior_filing_without_justificante -q --tb=short`
  - result: 2 passed.
- `uv run pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py -q --tb=short`
  - result: 28 passed.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -q --tb=short`
  - result: 171 passed.

## Live run status

The visible live runner still waits at the secure-storage passphrase prompt.
This exec record is local cross-period evidence hardening and does not claim a
new authenticated AEAT read.
