---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W02.P02.S02'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W02.P02.S02`

Classified the live AEAT browser-action inventory into authentication-only, read-only navigation/query, diagnostic cleanup, simulator-only, and forbidden live submission categories.

- Modified: `src/aeat/domain/calculations/registry/_remote_state_guard.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_renta_web_open.py`
- Modified: `src/aeat/core/external_constants.toml`
- Modified: focused registry/oracle/Renta tests
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`

## Description

Classification result:

- Authentication-only: Cl@ve selector authorization, non-QR identity entry, continue, auth target probe, storage-state capture.
- Diagnostic cleanup: pending Cl@ve cancellation after timeout, encrypted diagnostic capture, dialog handling.
- Read-only navigation/read: wallet selector GETs, Sede filed-history listing GETs, cotejo PDF GETs, notifications/walker/census page reads, CSV verification page GET.
- Read-only query submits: declarations `Buscar`, CSV verifier Enter, GROI/NIF-IVA consult submits. These are not filing submissions, but they must stay explicitly classified because they dispatch forms.
- Simulator-only actions: Renta WEB Open synthetic profile entry, accepted simulator identification, casilla navigation, casilla override fills, return to Resumen, summary/casilla scrape.
- Forbidden live submission: wallet execute submit, representation-gate submit, any declaration presentation/sign/payment/save/amend/cancel/upload/TGVI write action.

The implementation now attaches centralized allow-list patterns to registry policies built for GROI, NIF-IVA, and Renta WEB Open oracle cross-references. Renta WEB Open planned operations were expanded so casilla override and scrape navigation are visible to guard preflight instead of hidden inside the driver.

The plan state was inspected with `uv run vaultspec-core vault plan status` and `uv run vaultspec-core vault plan query`. The CLI can parse/query this L3 plan, but `step check` only accepts leaf ids and cannot uniquely close `W02.P02.S02` in this duplicated L3 id layout, so the exact display-path checkbox was updated directly after the CLI attempt failed for `W02.P02.S02`.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_remote_state_guard.py::test_remote_state_guard_blocks_unclassified_browser_action_when_allow_list_declared src/aeat/domain/calculations/registry/test_remote_state_guard.py::test_remote_state_guard_supports_allowed_browser_action_wildcards src/aeat/domain/calculations/registry/test_remote_state_guard.py::test_oracle_bound_cross_reference_policy_gets_consult_action_allow_list src/aeat/domain/calculations/registry/test_groi_oracle.py src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/test_groi_check.py src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py src/aeat/adapters/outbound/aeat/sede/test_renta_web_open_safety.py -q --disable-warnings` passed with 145 tests.
- `uv run ruff check src/aeat/domain/calculations/registry/_remote_state_guard.py src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/domain/calculations/registry/test_groi_oracle.py src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py src/aeat/core/external_constants.toml src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/_renta_web_open.py src/aeat/adapters/outbound/aeat/sede/test_renta_web_open_safety.py` passed.
