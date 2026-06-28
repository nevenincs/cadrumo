---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S139'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P19.S139 CLI parse-call-backend-render extraction

Scope:
- `src/aeat/application/modelo`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

Move remaining command-body business decisions in the active modelo work addressing surface behind application services, leaving the CLI to parse arguments, call backend services, translate refusals, and render envelopes.

## Changes

- Moved `work verify`, `work file`, and `modelo export` revision-state eligibility into application address resolvers:
  - `resolve_verifiable_modelo_calculation_revision_address`
  - `resolve_fileable_modelo_calculation_revision_address`
  - `resolve_exportable_modelo_calculation_revision_address`
- Moved `work compare-taxation` work-unit selection into `compare_taxation_for_work_address`.
- Moved `work calculate` persistence plus command-facing modality/authorization summaries into `calculate_modelo_work_revision`.
- Moved Modelo 202 modality summary rendering source into `modelo_202_modality_for_work_unit`.
- Moved stub-modelo create refusal policy and M210 live-engine exception into `_work_create_policy.py`.
- Moved work-create active-profile applicability refusal into `_work_create_policy.py`.
- Moved work-create active-profile foral CCAA guard into `_work_create_policy.py`.
- Moved work-unit plazo/recargo computation into `_work_plazo.py`; CLI now renders the returned summary.

## Verification

- `.venv\Scripts\python.exe -m py_compile src/aeat/application/modelo/_work_create_policy.py src/aeat/application/modelo/_work_plazo.py src/aeat/application/modelo/_calculate_input.py src/aeat/application/modelo/_taxation_comparison.py src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/__init__.py src/aeat/entrypoints/cli/_modelo.py`
- `.venv\Scripts\ruff.exe check src/aeat/application/modelo/_work_create_policy.py src/aeat/application/modelo/_work_plazo.py src/aeat/application/modelo/_calculate_input.py src/aeat/application/modelo/_taxation_comparison.py src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/__init__.py src/aeat/entrypoints/cli/_modelo.py --select F401,F821,E501,F811`
- `.venv\Scripts\pytest.exe src/aeat/application/modelo/test_selectors.py -q` - 13 passed.
- `.venv\Scripts\pytest.exe src/aeat/application/modelo/test_taxation_comparison.py src/aeat/entrypoints/cli/test_modelo_projection.py src/aeat/entrypoints/cli/test_modelo_compare.py src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py src/aeat/entrypoints/cli/test_modelo_export_verb.py -q` - 29 passed.
- `.venv\Scripts\pytest.exe src/aeat/entrypoints/cli/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/test_modelo_work_ux.py src/aeat/entrypoints/cli/test_work_calculate_borrador.py -q` - 25 passed.
- `.venv\Scripts\pytest.exe src/aeat/entrypoints/cli/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/test_modelo_work_ux.py -q` - 22 passed after the foral guard move.

## Discovery

- `vaultspec-rag server service status` reported the resident service healthy on port `8766`.
- RAG query through the resident service:
  - `.venv\Scripts\vaultspec-rag.exe search "_modelo.py CLI business logic work_create work_calculate plazo applicability" --type code --max-results 5 --port 8766`
- Exact closure audit:
  - No matches in `_modelo.py` for moved policy internals: `derive_modelo_applicability`, `ApplicabilityVerdict`, `_STUB_ONLY_MODELOS`, `derive_modelo_202_modality`, `AuthorizationState`, `resolve_filing_closes_on`, `build_recovery_for_overdue`, `calculate_modelo_revision_from_bucket_aggregation`, `compare_taxation_for_work_unit`, or revision-state checks.

## Residual

- `_modelo.py` remains monolithic and still has large command functions, especially because Typer option declarations are inline. This residual is assigned to W06.P20 decomposition and static size/complexity guards, not to backend policy relocation.
