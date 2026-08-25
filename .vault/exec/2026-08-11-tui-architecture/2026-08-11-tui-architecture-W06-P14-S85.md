---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f80d404f14169e0e9686681ec2e32ded4b505cab0ce7fef197b5d0fc4f4272d4'
step_id: 'S85'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Replace application flow parity dependencies on TUI modules with backend contract assertions

## Scope

- `src/cadrumo/application/flows/tests/test_frontend_parity.py`

## Description

- Delete the application-owned test that imported frontend implementation.
- Relocate three-frontend convergence, invalid-verdict, and section-copy parity proofs beneath the canonical TUI test owner.
- Retain engine, line-frontend, and localized-failure contracts beneath the application flow owner.
- Prove no application flow test imports the TUI package.

## Outcome

Application flow tests assert only frontend-neutral engine and line behavior. Frontend parity is exercised from `entrypoints.tui.tests.test_frontend_parity`, so the dependency points inward from the outer TUI boundary and no backend test reaches an entrypoint.

The focused backend and relocated parity selection passes 36 unit cases. RAG plus exact source/history audit found no remaining application-owned frontend parity file or TUI import. Independent review approved S85.

## Notes

The relocation landed through `0acec93b1a0`; the final cross-layer copy was deleted in `8c845ab92f`. No compatibility test module or import bridge was retained.
