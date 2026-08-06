---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:ac5dfa651560aacbd8da2d525c0809c20d755593caa604f95dc4d60ab29b2ff7'
step_id: 'S01'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `CalculationRevisionId`, `Dt12WindowEligibility`, `FilingRecordId`, `LedgerEvidenceRow`, `LedgerFilingEvidence`, `LedgerFilingSnapshot`, `LedgerFilingStalenessVerdict`, `LedgerRowFingerprint`, `ManualFactBasisEntry`, `Modelo184ShareSumError`, `Modelo347ThresholdError`, `ModeloError`, `ModeloExportError`, `ModeloValidationError`, `VerificationReportId`, `WorkUnitState`, `compute_dt12_reduccion_plan_pensiones`, `compute_sal_reserva_especial_dotacion`, `diff_ledger_fingerprints`, `dt12_regime_window_eligibility`, `m349_nif_number_for_export`, `snapshot_fingerprint`, `validate_m184_member_share_sum`, `validate_m347_threshold` to `aeat.domain.modelos.__all__` with eager re-exports so the 67 existing cross-package consumer site(s) can import from the facade

## Scope

- `src/aeat/domain/modelos/__init__.py`

## Description

- Ran `dev/import_hygiene_scan.py --json` and cross-confirmed with `rg` to
  identify the 24 symbols owned by `aeat.domain.modelos` reached cross-package
  through private submodules but absent from `aeat.domain.modelos.__all__`.
- Added eager `from ._submodule import Name` re-exports for each symbol,
  grouped alongside the existing per-submodule import blocks
  (`_dt12_reduccion`, `_errors`, `_ids`, `_ledger_filing_snapshot`,
  `_row_models`, `_sal_reserva_especial`, `_work_unit`).
- Extended `__all__` with all 24 promoted names; `ruff check --fix` confirmed
  the merged list needed no re-sorting.
- Made no behavioural changes; every promoted symbol's definition stays in its
  private submodule.

## Outcome

- Verified every one of the 76 names in `aeat.domain.modelos.__all__`
  (52 pre-existing + 24 promoted) resolves via `getattr`.
- `ruff check src/aeat/domain/modelos/__init__.py` passes clean.
- `pytest --collect-only -q src/aeat` reported 148 pre-existing collection
  errors, all tracing to one unrelated root cause: a concurrent peer's
  in-flight rename of `_period_sort_key` to `iva_compensation_period_sort_key`
  in `aeat.domain.iva_compensation._carry_forward` (confirmed via
  `git status --short` showing uncommitted peer WIP on that file, unrelated
  to this Step's scope). A second full-tree run after the peer's rename
  completed dropped to 1 remaining unrelated error
  (`_MODELO_303_IVA_COMPENSATION_BINDING_ID` missing from
  `aeat.application.calculations._binding_prefill`, also uncommitted peer WIP).
  A scoped `pytest --collect-only -q src/aeat/domain/modelos` collected 254
  tests with zero errors, confirming this Step's own surface is clean.
- Landed as commit `b05912011` touching only
  `src/aeat/domain/modelos/__init__.py`.

## Notes

- No underscore-prefixed symbols were among the 24 promotion targets, so the
  Ruling 3 per-symbol disposition procedure did not apply to this Step.
- No lazy `__getattr__` (PEP 562) idiom was introduced: the package already
  used eager imports exclusively and none of the promoted symbols risked a
  circular import (`_dt12_reduccion.py` and `_sal_reserva_especial.py` import
  only from `aeat.core` and sibling `._errors`).
- Wave W02 consumer-site rewrites onto this facade are out of scope for this
  Step and remain for the next phase.
