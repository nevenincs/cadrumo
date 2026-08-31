---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:990fa74565734ade459565674a6c1c33b8c1a9e3640fdfacd4e0992dc8beab68'
step_id: 'S127'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Refactor the size-budget subjects in acceleration_receipt.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py`
- `A` `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt_crypto.py`
- `M` `src/cadrumo/adapters/persistence/storage/_profile_login_session.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py`
- `M` `src/cadrumo/tests/test_session_vocabulary_custody_split.py`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S127.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt_crypto.py src/cadrumo/adapters/persistence/storage/_profile_login_session.py src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py src/cadrumo/tests/test_session_vocabulary_custody_split.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py src/cadrumo/tests/test_session_vocabulary_custody_split.py` -> `pass` (42 passed)
- `verify:` `uv run --no-sync python -c "from cadrumo.tests._size_budget import MODULE_POLICY, measure_module_lines; p='src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py'; actual=measure_module_lines()[p]; assert actual <= MODULE_POLICY.default_limit, (actual, MODULE_POLICY.default_limit); print(f'{p}: {actual} lines <= default {MODULE_POLICY.default_limit}')"` -> `pass` (1065 <= 1250)

## Notes

`uv run --no-sync python -m dev.audit.size_budget` exits 1 for 88 remaining live size-budget findings; `acceleration_receipt.py` is absent from those findings and this step does not regenerate or raise the baseline.

