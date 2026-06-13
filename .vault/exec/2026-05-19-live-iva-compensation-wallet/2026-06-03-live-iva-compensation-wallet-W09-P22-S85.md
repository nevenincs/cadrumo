---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S85'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# Modelo 303 Wallet-Only Export Coverage

Scope: `src/aeat/_data/registry/aeat/modelos/303`, `src/aeat/application/filing`, `src/aeat/application/modelo`, `src/aeat/entrypoints/cli`.

## Description

- Re-checked the current Modelo 303 registry tree and found existing fichero-BOE export-layout TOML for both active revision families.
- Added non-private `wallet_only` coverage that uses production `create_work_unit`, `calculate_modelo_revision`, `mark_revision_verificado_completo`, and `export_modelo_revision`.
- Persisted a synthetic non-blocking AEAT wallet authority decision before calculation so the lifecycle matcher sees the same authority source that calculation consumed.
- Asserted the local exported fichero is written and carries normal declaration data while the application result and bucket event carry only redacted wallet decision refs, authority, divergence, target, and source hashes.
- Corrected stale audit and plan wording that treated Modelo 303 export support as absent.

## Outcome

`S85` is complete. The registry-backed Modelo 303 export happy path is no longer provisional for wallet-only IVA compensation coverage.

## Notes

No live AEAT contact was made. No private taxpayer values or live amounts were added to code or tests. The first two failed executions were real fixture-readiness failures: the draft builder requires a valid Spanish tax identifier, and Modelo 303 export approval requires complete formula trace inputs plus the operator surname profile fact.

Remaining work stays open in `S82` for opt-in live read-only AEAT regression and `S83` for the local file workflow harness.
