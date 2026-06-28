---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S270]]'
---

# `secure-storage-production-hardening` `W12.P26.S270` Review

## S270-001 | PASS | Repository exceptions are typed and sanitized

Profile record miss, profile snapshot miss, inner envelope classification mismatch, and inner envelope schema-version mismatch now raise AEAT-derived typed exceptions with stable messages. Raw profile and snapshot identifiers remain out of `str(error)` and stay in structured context for redacted envelopes.

## S270-002 | PASS | Localization is enrolled through the canonical CLI

The repository-specific message keys were added to `en`, `es`, `ca`, and `hu` via `python -m aeat.locales`. The same audit pipeline removed stale modelo work extras and now reports every locale as clean.

## S270-003 | PASS | Tests exercise real storage behavior

The repository tests write real secure-object records with deliberately mismatched inner envelopes, then load through the public repository APIs. The assertions verify exception type, translated-message key, context evidence, and absence of identifier leakage without fakes, monkeypatches, or duplicated business logic.

## S270-004 | OBSERVE | Cache invalidation import fallback remains best-effort

The output-language cache invalidation path narrows import fallback to `ImportError` and logs that fallback at debug level. Runtime failures from the imported invalidator are not swallowed, which keeps real defects visible instead of hiding them behind the best-effort cache path.

## S270-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/user_profile/_repository.py src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_repository_anti_tautology.py src/aeat/application/user_profile/test_repository_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_repository_anti_tautology.py src/aeat/application/user_profile/test_repository_roundtrip.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

## S270-006 | PASS | Delegated review finding resolved

The delegated reviewer flagged that three modelo work translation keys had been removed while still referenced. Those keys were retained through the canonical locale CLI, and only audit-reported unreferenced modelo work extras were removed. The final locale audit reports `ok` for every locale.

Disposition: close `AFR-168`.
