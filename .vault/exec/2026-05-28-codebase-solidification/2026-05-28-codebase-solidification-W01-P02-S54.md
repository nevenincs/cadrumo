---
step_id: S54
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S54 — error-registry logger scrubbing test

## Outcome

Extended `src/aeat/core/errors/test_registry.py` with three real-behavior tests
for the module-level `logger` in `_registry.py`:

- `test_error_registry_logger_is_module_level` — asserts `_registry.logger` is
  a `logging.Logger` instance with the correct module `name`.
- `test_error_registry_debug_log_scrubs_sensitive_context` — emits a DEBUG
  record carrying `oauth_refresh_token=abc-secret-xyz`, captures via `caplog`,
  asserts the token value is absent and `<redacted>` present. Calls
  `configure_logging()` and ensures the root `SecretScrubbingFilter` is present
  before the assertion.
- `test_error_registry_debug_log_scrubs_nif_in_context` — same pattern for a
  NIF-shaped arg (`tax_id=12345678Z`).

Since `_registry.py` cannot use `get_logger` at module load (circular import),
the filter arrives via root-logger propagation; the tests verify this path is
functional end-to-end.

## Files touched

- `src/aeat/core/errors/test_registry.py`

## Verification

`uv run --no-sync pytest src/aeat/core/errors/test_registry.py -xvs -k "not sphinx_role and not broken_fragments"` — 7 passed.
`vault plan step check S54` applied.
