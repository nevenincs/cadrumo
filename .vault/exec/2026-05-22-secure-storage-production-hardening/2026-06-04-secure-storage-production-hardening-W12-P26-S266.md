---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S266'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s266-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S266`

Closed `AFR-164` for active-profile output-language resolver wiring.

## Description

- Audited `src/aeat/application/user_profile/_language_resolver.py` as an active-profile manifest-discovery callback into `core.i18n`.
- Verified the resolver performs only a read path and defers heavyweight workflow/orchestration imports inside the resolver body.
- Verified `src/aeat/core/i18n/_render.py` treats the registered callback as best-effort, logs resolver failures at debug level through the central scrubbed logger, and falls back to settings/default language.
- Confirmed the package-level lazy-boundary test still passes.
- Closed `S266` through `vaultspec-core vault plan step check` and manually aligned `AFR-164`.

## Outcome

`AFR-164` is closed with no production code changes. The resolver is correctly enrolled as a manifest-discovery surface: active-profile language lookup is optional, read-only, centrally registered, and fail-soft at the core i18n boundary.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_language_resolver.py src/aeat/core/i18n/_render.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_lazy_boundary.py src/aeat/core/i18n/test_translatable_contract.py`

Validation caveat:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_language_resolver.py src/aeat/core/i18n/_render.py src/aeat/application/user_profile/test_lazy_boundary.py` still reports the pre-existing `S603` subprocess finding in `test_lazy_boundary.py`.

## Notes

The plan check still reports the existing `PLAN022` monotonic-order warning only.
