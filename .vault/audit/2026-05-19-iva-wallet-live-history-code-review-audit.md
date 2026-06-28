---
tags:
  - '#audit'
  - '#iva-wallet-live-history'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-04-12-modelo-303-390-research]]'
  - '[[2026-04-12-modelo-303-390-adr]]'
  - '[[2026-04-12-modelo-303-390-plan]]'
---

# `iva-wallet-live-history` Code Review

IVA-WALLET-001 | MEDIUM | Resolved: submitted-file capture errors did not preserve filed evidence

The first review pass found that submitted-file download failures were only degraded when `_capture_submitted_file_artefact` raised `SedeNavigationError`. Empty-body downloads raise `JustificanteFetchError`, so the filed observation could still abort after the register row and justificante had already been captured. The handler now records both `SedeNavigationError` and `JustificanteFetchError` in `submitted_file_capture_error`, preserving the official evidence envelope without promoting missing casillas into calculation history.

IVA-WALLET-002 | LOW | Residual: capture-failure preservation is not browser-flow tested

The focused tests cover filed-observation promotion, duplicate filing selection, cross-year Modelo 303 recurrence, wallet reconciliation, and real Modelo 303 engine consumption. They do not drive the Playwright download failure branch directly. A browser-flow regression test remains desirable, but should use the real adapter surface rather than a fake page, mock, monkeypatch, or tautological helper assertion.

IVA-WALLET-003 | REVIEW | No high-risk issue found in cross-year compensation semantics

The review found the year-wrap fix coherent: 2026 1T now resolves the immediately previous Modelo 303 period as 2025 4T in both previous-filing bindings and relation requirements. This matches AEAT Modelo 303 instructions for casilla 110 as compensation pending from previous periods and the Pre303 wallet framing.
