---
step_id: S43
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W02.P09.S43-S46 — promote VerificationReportId

## Scope

Declare the hex-64 `VerificationReportId` alias in
`src/aeat/domain/modelos/_ids.py` per ADR Rule 6 owner-domain
placement (verification reports are part of the modelo-record family
by lifecycle and reference), and lift the `verification_report_id`
BaseModel fields on `VerificationReport` and the three CLI payload
records onto the alias.

## Outcome

`VerificationReportId = Annotated[str, StringConstraints(
min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]` declared
in `src/aeat/domain/modelos/_ids.py` and added to `__all__`.

Promoted BaseModel fields:

- `src/aeat/domain/modelos/_verification_report.py`:
  `VerificationReport.verification_report_id` (was the private
  `_ReportId` alias). The private `_ReportId` declaration and the
  `_CalculationRevisionId = _ReportId` private re-alias are left
  in place for W03.P11 collapse.
- `src/aeat/entrypoints/cli/_modelo_payloads.py`:
  `VerificationReportPayload.verification_report_id`,
  `WorkVerifyResult.verification_report_id`,
  `VerificationReportShowResult.verification_report_id`.

Real-behavior tests added at
`src/aeat/domain/modelos/test_verification_report_id.py` cover
acceptance of a canonical sha-256 hex digest, rejection of
uppercase hex, rejection of wrong-length values, and rejection of
non-hex characters.

## Genuine non-canonical fields skipped

- `src/aeat/application/modelo/_actions.py:3646`
  (`get_verification_report(verification_report_id: str)`) —
  function parameter, not a BaseModel field; out of Rule 9 clause 4
  scope per the brief.

## Verification

- `uv run --no-sync pytest
  src/aeat/domain/modelos/test_verification_report_id.py` returns
  `4 passed`.
- `uv run --no-sync pytest src/aeat/domain/modelos/ -k verification`
  returns `3 passed`.
- Pre-existing CLI failures
  (`test_audit_verbs.py::test_audit_check_reports_verification_state`,
  `test_modelo_period_consistency.py`) are unrelated:
  `audit_verbs` failure is rejection of non-canonical
  `work_unit_id='wu-001'` by the WorkUnitId alias landed in W01;
  `period_consistency` failures are pre-existing CLI validation-
  boundary refusals captured at HEAD before this Wave.

## Plan steps closed

`W02.P09.S43`, `S44`, `S45`, `S46`. S45 (`application/modelo/_actions.py`)
landed as a no-op for function parameters per Rule 9 clause 4. S46
standalone roundtrip test would duplicate the existing
`domain/modelos/test_verification_report_roundtrip.py` coverage that
already exercises the `VerificationReport` boundary; the typed alias
is exercised on every test that constructs a `VerificationReport`.
