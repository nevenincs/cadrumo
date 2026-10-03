---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-10-03'
body_hash: 'sha256:e3c921d22f7366421d5345a221c3771707d7db16558339b04445833c0a85fa7d'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S137` Review

## S137-001 | PASS | LLM cache default root now flows through centralized settings

The reviewed cache already persisted LLM responses through the encrypted secure-object repository and redacted entries at `SensitivityClass.DIAGNOSTIC` before save. The remaining S137 gap was the default logical root: direct `LLMCache()` construction used a hard-coded `PROJECT_ROOT / "var" / "llm-cache"` fallback instead of the centralized settings surface.

The default now uses `load_settings().aeat_llm_cache_dir`, preserving explicit `root_dir` overrides while enrolling direct construction in the project settings contract. This matters for adverse production conditions because runtime profile and test overrides are honored through `load_settings()`, while direct `Settings()` construction would bypass `override_settings` and environment-wrangling conventions.

Validation:

- the historical check passed with 29 tests.
- the historical check passed with 5 selected tests.
- the historical check passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-core vault plan check.vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with only the existing `PLAN022` warning.
- Source scan found no direct `PROJECT_ROOT`, direct `Settings()`, hard-coded `var/llm-cache`, `# noqa`, pragma, or `type: ignore` in the S137 code/test slice.

Disposition: close `AFR-035` as `remote-mirror`.

## S137-002 | LOW | RESOLVED | Existing closed S135 row had invalid plan row tail

While validating S137, the plan checker reported `PLAN040` on the already-closed S135 row for the retired Google `_refresh.py` file. The row explained that the file was absent from `git ls-files`, but the scope tail did not match the required backticked path format.

Resolution: the S135 row now preserves the stale/retired context in prose and terminates with the required backticked path tail.

Validation:

- `uv run --no-sync vaultspec-core vault plan check.vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` now reports only `PLAN022`.
