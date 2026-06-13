---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-27-live-iva-compensation-wallet-w05-p13-s45-live-auth-preflight-exec]]'
  - '[[2026-05-27-live-iva-compensation-wallet-w05-p13-s46-auth-route-diagnostics-exec]]'
---

# `live-iva-compensation-wallet` Code Review

LIVEIVA-AUTH-DIAG-001 | MEDIUM | RESOLVED | Preflight rendering did not cover all authenticated live-read CLI paths

Initial review found the redacted auth preflight rendered before IVA wallet pull
and capture-history, but not before filed-history list/capture/capture-sources,
DEHu notifications capture, or expedientes capture. Those commands can also
trigger the authenticated AEAT session path and therefore need the same operator
profile/auth-route visibility before a Cl@ve wait begins. The preflight is now
called before each of those live-read entrypoints. Public verify surfaces that
use direct read gates rather than the authenticated session helper were left
unchanged.

LIVEIVA-AUTH-DIAG-002 | INFO | REVIEWED | No raw DNI/NIE or support-number values surfaced by the new preflight report

The preflight report exposes presence flags, identity kind, alignment state,
route mode, timeout, certificate state, active-profile references, and
persisted-session state. It does not include raw DNI/NIE or support-number
fields. The focused test asserts the synthetic DNI/NIE and support marker do
not appear in the report JSON.

## Verification

- `uv run pytest -q src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_diagnostics.py` passed.
- `uv run ruff check src/aeat/application/auth/_operator.py src/aeat/application/auth/__init__.py src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_diagnostics.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/entrypoints/cli/_app_live.py` passed.
- Follow-up `uv run ruff check src/aeat/entrypoints/cli/_app_live.py` passed after expanding preflight coverage.
