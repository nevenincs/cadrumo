---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S452'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W20.P40.S452 - Harden passphrase bootstrap and redaction

Scope: close the passphrase environment bootstrap, central redaction, and residual
custody-test environment observations adopted from the secure-storage observation
pool.

## Description

- Verified passphrase resolution now goes through `Settings` and the fail-closed
  unset path exercises the real prompt boundary without monkeypatching or fake
  callbacks.
- Verified the custody CLI integration harness passes test passphrases as an
  in-process subprocess argument and then into `Settings`, avoiding secret env
  handoff while preserving real CLI behavior.
- Hardened the central log assignment redactor so quoted and unquoted multi-word
  passphrase assignments are redacted as a whole sensitive value.
- Added real logging-filter coverage proving multi-word passphrase assignments are
  removed while adjacent non-sensitive assignment context remains visible.
- Audited the remaining custody-test environment use and documented it as harness
  isolation for non-secret `AEAT_ACTIVE_PROFILE` precedence, not passphrase custody.

## Outcome

The historical passphrase observation is closed for the current runtime custody
surface. Production passphrase bootstrap remains centralized through
`load_settings()` / `override_settings`, tests no longer pass passphrase material
through `AEAT_TEST_SECRET_PASSPHRASE`, and central logging redaction no longer leaks
words after the first space in assignment-shaped passphrases.

Validation:

- `uv run --no-sync pytest src/aeat/core/tests/test_logging.py -q`
- `uv run --no-sync ruff check src/aeat/core/logging.py src/aeat/core/tests/test_logging.py`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py src/aeat/adapters/persistence/storage/master_key/tests/test_master_key.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py -m integration -q`
- `uv run --no-sync ruff check src/aeat/core/logging.py src/aeat/core/tests/test_logging.py src/aeat/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

The remaining `os.environ` reference in the custody lifecycle test is limited to
constructing a sanitized subprocess environment and to non-secret active-profile
precedence checks. The secret passphrase itself is now supplied through the harness
argument path and converted into `Settings` inside the subprocess.

`vaultspec-core vault plan check` still reports the existing `PLAN022` monotonic
identifier warning; no new plan-structure warning was introduced by S452.
