---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W02.P02.S01'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W02.P02.S01`

Enumerated the current live AEAT browser-action surface and converted the highest-risk unclassified wallet/declarations/CSV guard paths to explicit action allow-lists.

- Modified: `src/aeat/domain/calculations/registry/_remote_state_guard.py`
- Modified: `src/aeat/core/external_constants.toml`
- Modified: `src/aeat/core/external_constants.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- Modified: `src/aeat/adapters/outbound/aeat/verify/__init__.py`
- Modified: focused tests for the files above
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`

## Description

The inventory covered live `goto`, `navigate`, `request.get`, `click`, `fill`, `press`, `type`, `evaluate`, `expect_page`, `expect_download`, and POST-capable paths under `src/aeat/adapters/outbound/aeat`.

Observed action classes:

- Authentication-only: Cl@ve selector authorization, non-QR identity fields, continue, pending-request cancellation, storage-state capture.
- Read-only navigation/read: wallet selector navigation, declarations listing, cotejo PDF GET, notifications and expediente detail GETs, CSV verification page GET.
- Read-only query submits requiring explicit review: declarations `Buscar`, CSV verifier Enter, GROI/NIF-IVA consult submits.
- Simulator-only interactions requiring explicit review: Renta WEB Open synthetic-profile fields, accepted simulator identification, casilla navigation and override fills.
- Forbidden live submission candidates: wallet execute submit and representation-gate submit remain blocked.

Implemented the first hardening slice by adding `allowed_browser_action_patterns` to `RemoteStateGuardPolicy`. Policies that opt in now reject browser actions not present in their explicit allow-list after the canonical write-token denylist has run. The accepted action patterns for wallet, declarations, CSV verification, consult oracles, auth, and Renta WEB Open now live in `external_constants.toml`; wallet, declarations, declaration snapshot-derived policies, and CSV verification consume those constants.

The remaining W02.P02 steps are still open because auth cleanup, GROI/NIF-IVA consult drivers, Renta WEB Open, and walker expansion still need full runtime wiring to the centralized allow-list rather than inventory-only classification.

The vault CLI was unavailable in this environment (`vault` command not found), so the plan checkbox for this completed inventory step was updated directly.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py src/aeat/adapters/outbound/aeat/verify/test_verify.py -q --disable-warnings` passed with 115 tests.
- `uv run ruff check src/aeat/domain/calculations/registry/_remote_state_guard.py src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py src/aeat/adapters/outbound/aeat/verify/__init__.py src/aeat/adapters/outbound/aeat/verify/test_verify.py` passed.
