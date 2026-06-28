---
tags:
  - '#audit'
  - '#continuous-review'
date: '2026-04-20'
modified: '2026-04-20'
related:
  - '[[2026-04-18-auth-protocol-adr]]'
  - '[[2026-04-18-auth-protocol-plan]]'
  - '[[2026-04-18-auth-protocol-review-audit]]'
---

# `continuous-review` Code Review

## Findings

### AUTH-001 | MEDIUM | Dead certificate backends remained in the public settings contract

- Scope: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate.py`, `env/.env.example`
- Summary: `CertificateBackend` still exposed `USER_DATA_DIR` and `MTLS_PROXY` even though both implementations were hard `NotImplementedError` stubs. That left dead values in the runtime settings and setup wizard choice list, so invalid operator configuration failed late instead of being impossible to select.
- Fix: removed both enum values, deleted the dead backend modules, narrowed backend dispatch to the two real implementations, updated the env example comment, and added a regression test proving settings reject the removed backend names.

## Verification

- `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate.py tests/test_config.py src/aeat/application/setup/test_wizard.py -q` -> passed (`38 passed`)
- `uv run pytest -q -W error::DeprecationWarning src/aeat/auth src/aeat/submission src/aeat/workflow src/aeat/setup tests/test_config.py` -> passed (`216 passed, 5 deselected`)
- `uv run pytest -m unit -q` -> passed (`1878 passed, 1 skipped, 28 deselected`)
- `uv run ruff check .` -> passed
- `uv run ty check .` -> passed
- Residual warning surface: third-party `ofxparse` emits `DeprecationWarning` from site-packages during the full unit suite. No in-repo deprecation findings remain in the audited domains.

## Status

- No additional actionable findings remain in this pass for safety, code duplication, shadowing, test stubbing, or in-repo deprecation burden.
