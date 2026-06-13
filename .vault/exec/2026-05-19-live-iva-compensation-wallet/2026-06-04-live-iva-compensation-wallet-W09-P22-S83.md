---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S83'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]'
  - '[[2026-05-26-live-iva-auth-read-acquisition-adr]]'
---

# Wallet-Only Local File Lifecycle

Scope: `src/aeat/application/modelo`, `src/aeat/domain/period`, `.vault/audit`, `.vault/exec`.

## Description

- Added non-private local lifecycle coverage for a Modelo 303 `wallet_only` authority decision.
- Used the real Cl@ve provider selection path with synthetic local settings so the workflow preflight calls provider `describe()` without browser work, live authentication, or AEAT contact.
- Exercised production reconciliation, Modelo 303 calculation, verified-complete promotion, and `file_modelo_revision()` with real repositories.
- Asserted the resulting local filing record remains internal-only: not AEAT accepted and without external AEAT filing evidence.
- Fixed the period-token mismatch the test exposed: Modelo 303 work-unit periods now map to the deadline-engine `YYYY-nT` token, and the central period parser accepts that token for downstream registry resolution.
- Aligned the file-flow test harness period producer with the production mapping.

## Outcome

Focused gates passed:

- `uv run pytest src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_wallet_only_modelo_303_can_be_locally_filed_with_real_clave_provider_preflight -q`
- `uv run pytest src/aeat/domain/test_period.py -q`
- `uv run pytest src/aeat/application/modelo/test_actions.py::TestWorkflowInputMismatchError src/aeat/domain/test_period.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_wallet_only_modelo_303_can_be_locally_filed_with_real_clave_provider_preflight -q`
- `uv run pytest src/aeat/application/modelo/test_file_flow.py::test_verify_records_deadline_state_as_informational_not_abort src/aeat/application/modelo/test_file_flow.py::test_file_still_refuses_a_closed_past_period_no_pending_obligation -q`
- `uv run ruff check src/aeat/domain/period.py src/aeat/domain/test_period.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_actions.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py`

## Notes

No AEAT live request, authentication prompt, filing, payment, confirmation, or represented-taxpayer action was performed in this step.

The first local lifecycle attempt failed honestly with `NO_PENDING_OBLIGATION` because the application mapped Modelo 303 `2T` work units to `2026Q2` while the deadline engine emits `2026-2T`. The fix keeps the deadline-engine/projection contract intact and updates the Modelo workflow boundary to use the same token.

Live read-only verification remains tracked separately in `S82`.
