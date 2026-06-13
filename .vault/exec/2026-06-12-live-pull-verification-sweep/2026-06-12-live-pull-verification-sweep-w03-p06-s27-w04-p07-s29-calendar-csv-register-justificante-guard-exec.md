---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
plan: '[[2026-06-12-live-pull-verification-sweep-plan]]'
step_id: W03.P06.S27
related_steps:
  - W04.P07.S29
---

# W03.P06.S27 calendar CSV-register justificante guard

## Scope

Added CLI regression coverage proving that an imported AEAT CSV/register
baseline remains only AEAT-accepted/observed calendar evidence until a matching
justificante is verified.

This closes an operator-surface coverage gap around the application filing
semantics split: an application filing record can carry AEAT-side evidence, but
the calendar must still refuse strict rendering when that evidence is not
justificante-backed.

## Code changes

- `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  - extended the existing external-evidence helper to accept an
    `ExternalEvidenceKind`;
  - added
    `test_calendar_strict_mode_refuses_imported_csv_register_without_justificante`.

The regression uses the real profile storage session and
`ModeloRecordCatalogueRepository`, stamps censo enrolment provenance to keep
the test focused on the filing axis, then seeds a current Modelo 303 record
with:

- `aeat_accepted=True`;
- `external_evidence.kind=aeat_csv_register`;
- no matching persisted justificante metadata.

Strict calendar mode refuses with `filing.justificante_unverified`.
`--allow-incomplete --format json` exposes the row as:

- `local_filing_state=external_baseline_imported`;
- `aeat_submission_state=accepted`;
- `aeat_evidence_kind=aeat_csv_register`;
- `justificante_verified=false`.

No production transport, live-read gate, command verb, or `pull`/`pull-all`
surface changed.

## Verification

Required semantic discovery was attempted first:

- `vaultspec-rag search --timeout 180 "cross period clean state AEAT CSV register justificante verified filing evidence calendar modelo"`
  - result: `http_search_timeout`.

Focused local gates:

- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_strict_mode_refuses_imported_csv_register_without_justificante -q -rs --tb=short`
  - result: 1 passed.
- `.venv\Scripts\python.exe -m ruff check src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  - result: passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q -rs --tb=short`
  - result: 15 passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_csv_register_evidence_still_requires_justificante_verification src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_cross_period_clean_state_blocks_csv_register_without_justificante_verification -q -rs --tb=short`
  - result: 2 passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py::test_verify_modelo_390_refuses_csv_register_prior_filing_without_justificante -q -rs --tb=short`
  - result: 1 passed.

## Plan status

This strengthens local calendar and cross-period evidence coverage. It does
not close live rows because positive authenticated AEAT censo/filed/justificante
pull evidence is still outstanding.
