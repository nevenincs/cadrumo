---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
step_id: 'S77'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-test-hygiene-audit]]'
  - '[[2026-05-26-secure-storage-settings-route-audit]]'
  - '[[2026-05-26-secure-storage-model-duplication-audit]]'
  - '[[2026-05-26-secure-storage-exception-observability-audit]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `secure-storage-production-hardening` `W11.P19.S77`

Added focused regression guards for the secure-storage convention-hardening repairs.

## Changes

- Added `src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`.
- Guarded bucket-session cleanup observability against `noqa`, coverage pragmas, `pass`, traceback logging, and warning-log removal.
- Guarded named bucket settings derivation so storage runtime cannot regain pydantic field-set mutation and must continue delegating to the central settings helper.
- Guarded fresh profile-bucket KDF defaults so the profile repository continues deriving manifest parameters from canonical `KdfParams`.
- Guarded W11 hardening tests against skip/xfail shortcuts, fake/stub classes, mock imports, and unapproved environment access.
- Added secure-storage error registry locale-key coverage by checking every `SecureStorageError` subclass has a registered message key present in every locale file.
- Tightened the guard after review to cover pytest marker attributes, `mock` import variants, `os` aliases, `from os import environ`, direct environment subscript mutation, environment method calls, `os.putenv`/`os.unsetenv`, and simple constant-indirected environment keys.

## Validation

- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py -q`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py src/aeat/core/test_settings_single_surface_invariant.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py src/aeat/core/test_settings_single_surface_invariant.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py -q`
- `uv run python -m aeat.locales scaffold --check`
- `uv run python -m aeat.locales audit`

## Review

The targeted S77 review initially found guard false negatives around pytest marker forms, mock import variants, environment aliasing, and environment mutation methods. Those findings were repaired. Final review reported only dead helper cleanup, which was removed before the final validation pass.
