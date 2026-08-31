---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:b5ab5e1ce9bf73614d85a6109414aa2afc66da9074f601e0bfb5a3dabc67f29d'
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
- `verify:` `git diff-tree --no-commit-id --name-only -r 1024192354` derived the six immutable S127 Python paths, excluding current peer-owned `src/cadrumo/adapters/persistence/storage/_profile_login_session.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt_crypto.py src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py src/cadrumo/tests/test_session_vocabulary_custody_split.py` -> `pass` (`All checks passed!`; exit 0)
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt_crypto.py src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py src/cadrumo/tests/test_session_vocabulary_custody_split.py` -> `pass` (`6 files already formatted`; exit 0)
- `verify:` `uv run --no-sync pytest --collect-only -q -o "addopts=" src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py src/cadrumo/tests/test_session_vocabulary_custody_split.py` -> `pass` (`51 tests collected in 0.39s`; exit 0; zero deselected)
- `verify:` `pytest invocation over the 42 explicit collected non-os_keychain node IDs with -q -o "addopts="` -> `pass` (`42 passed in 11.76s`; exit 0; zero deselected)
- `verify:` `uv run --no-sync pytest -q -o "addopts=" src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py src/cadrumo/tests/test_session_vocabulary_custody_split.py` -> `fail` (`9 failed, 42 passed in 11.43s`; exit 1; zero deselected)
- `verify:` `uv run --no-sync python -c "from cadrumo.tests._size_budget import MODULE_POLICY, measure_module_lines; p='src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py'; actual=measure_module_lines()[p]; assert actual <= MODULE_POLICY.default_limit, (actual, MODULE_POLICY.default_limit); print(f'{p}: {actual} lines <= default {MODULE_POLICY.default_limit}')"` -> `pass` (1065 <= 1250)

## Notes

`uv run --no-sync python -m dev.audit.size_budget` exits 1 for 88 remaining live size-budget findings; `acceleration_receipt.py` is absent from those findings and this step does not regenerate or raise the baseline.

The recorded all-marker collection clears the repository's default `unit and not external_tool and not os_keychain` filter only to prove that every explicit focused test was selected. The 42 non-`os_keychain` node IDs were then invoked explicitly, rather than selected by a marker expression, so their passing run has no deselection state. The nine selected `os_keychain` cases fail on this agent's real Windows credential store with `WinError 1312` (`KeyringUnavailableError`); project configuration assigns that capability to the interactive-desktop-only `just test-os-keychain` lane. The formatter proof is limited to immutable S127 commit paths because the present worktree copy of `_profile_login_session.py` belongs to a peer and would be reformatted; this evidence-only repair intentionally does not alter it.

