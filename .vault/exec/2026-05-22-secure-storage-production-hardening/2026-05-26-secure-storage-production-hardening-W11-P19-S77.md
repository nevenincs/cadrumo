---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S77'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-s75-code-review-audit]]'
  - '[[2026-05-26-secure-storage-settings-route-audit]]'
  - '[[2026-05-26-secure-storage-model-duplication-audit]]'
---



# `secure-storage-production-hardening` `W11.P19.S77`

Added static hardening guards for the convention repairs completed in W11.

## Changes

- Added guard coverage for bucket-session cleanup observability, centralized settings route derivation, canonical KDF model reuse, hardening test shortcut markers, environment access, fake/stub/mock imports, and secure-storage error registry locale bindings.
- Included the S75 master-key and blob materialisation test surfaces in the test-hygiene guard.
- Kept the passphrase environment parser tests as an explicit allowlisted production-boundary exception, matching the S75 review disposition.

## Validation

- `uv run ruff check src\aeat\adapters\persistence\storage\test_hardening_convention_guards.py`
- `uv run pytest src\aeat\adapters\persistence\storage\test_hardening_convention_guards.py -q`
- `uv run python -m aeat.locales audit`
