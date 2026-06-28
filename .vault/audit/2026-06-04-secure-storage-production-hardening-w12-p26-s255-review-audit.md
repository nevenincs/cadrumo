---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S255]]'
---

# `secure-storage-production-hardening` `W12.P26.S255` Review

## S255-001 | HIGH | Ledger-preflight skip on registry snapshot absence was silent

`_modelo_requires_ledger_preflight` caught missing or invalid registry snapshots and returned `False`, which silently skipped ledger preflight for modelo readiness. The branch now logs a DEBUG record with non-secret modelo/year/period context before preserving the non-fatal skip behavior.

## S255-002 | MEDIUM | Active bucket id was formatted into a debug message

The active-profile label resolver logged the raw bucket id in the message template when manifest lookup failed. The log now omits the raw bucket id from the rendered message while preserving exception details through the centralized logger.

## S255-003 | MEDIUM | Unknown auth-provider probe logged caller selector through traceback

`_build_auth_readiness` previously relied on `AuthProviderKind(provider)` raising `ValueError` for an unknown requested provider, then logged the probe failure with `exc_info=True`. Direct API callers could supply arbitrary selector text, and the exception traceback would include that raw selector. The projection now detects unknown provider tokens before enum coercion, logs a generic warning, and reports the backend unavailable without rendering the token.

## S255-004 | PASS | Projection stays read-only and centralized

`build_operator_state_projection` remains the single read-projection producer. It loads profile, auth, workspace, deadline, and modelo-readiness state without writing stores; storage write ownership stays in the underlying profile, workflow, and repository services.

## S255-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/state_projection.py src/aeat/application/test_state_projection.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/test_state_projection.py` passed with 15 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-153` as `remote-mirror` with projection diagnostics hardened.
