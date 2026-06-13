---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# Live IVA Wallet Review Fixes

Implemented follow-up fixes from the 2026-06-03 code review:

- Wallet parser now rejects an executed shell without an explicit AEAT zero aggregate instead of synthesizing zero evidence.
- Wallet parser validates rendered `Ejercicio` and `Periodo` labels when present.
- Representation-gate continuation now inspects form action, method, own-name controls, and representative selection before submit.
- Wallet query form now fails closed when required ejercicio/periodo fields are absent.
- Wallet diagnostics now persist only redacted structural metadata, never raw HTML, frame HTML, screenshots, input values, or wallet amounts.
- Wallet action labels now come from centralized external constants.
- Wallet reconciliation accepts and threads an explicit decision repository and defaults to the same secure-object repository as the recurrence repository.
- Modelo 303 verification/export/file gates now require persisted non-blocking wallet authority matching the revision compensation amount.
- Modelo 303 export results and export bucket events now carry redacted IVA wallet decision provenance using authority, divergence, target period, and hash references only.
- Review cleanup removed stale private blocked-only lifecycle helpers so the strict matcher is the single Modelo 303 wallet authority gate.
- Added non-private `wallet_only` real-engine coverage from reconciliation through Modelo 303 calculation and lifecycle authority matching.
- Added non-private full Modelo 303 `wallet_only` export coverage through create, calculate, verify, and `export_modelo_revision` against the registry-backed fichero layout.
- Backend test arithmetic was replaced with direct persisted-field assertions.

Verification:

- `ruff check` passed for all touched source and test files.
- Focused `pytest` passed for wallet parser, external constants, backend wallet capture, Modelo 303 lifecycle, and export gates: 123 passed.
- Modelo 714 registry drift was resolved by removing the empty Phase-A formulas fragment that blocked global registry loading.

Remaining work:

- Live read-only AEAT regression remains open as `S82`.
- Downstream local-file lifecycle coverage for the live-observed `wallet_only` path remains open and is tracked as `S83`.
