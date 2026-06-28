---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S63'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W09.P16.S63`

Inventoried dirty and untracked secure-storage-related artifacts against current plan coverage.

- Created: `.vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-26-secure-storage-production-hardening-W09-P16-S63.md`

## Description

The secure-storage-related inventory from the worktree is:

- Storage primitive and runtime files: `src/aeat/adapters/persistence/storage/__init__.py`, `runtime.py`, `test_runtime.py`, `errors.py`, `envelope/_secure_repository.py`, `sql/__init__.py`, `sql/secure_objects.py`, `sql/test_secure_objects.py`, `test_submission_repository.py`.
- Bucket and custody files: `bucket/__init__.py`, `bucket/_errors.py`, `bucket/_manifest.py`, `bucket/_manifest_io.py`, bucket tests, `master_key/_active_session.py`, `master_key/_bucket_session.py`, `master_key/_master_key.py`, `master_key/_recovery_facade.py`, `master_key/test_idle_timeout.py`, and `master_key/test_master_key.py`.
- Operator route and custody surfaces: `src/aeat/core/config.py`, `src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py`, `src/aeat/entrypoints/cli/test_root_fallback_write_guard.py`, `src/aeat/entrypoints/cli/_config/test_bucket_history_parsing.py`, `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`, and `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`.
- Application readiness and repair surfaces: `src/aeat/application/auth`, `src/aeat/application/repair_integrity.py`, `src/aeat/application/state_projection.py`, `src/aeat/application/workflow/_profile_bucket_scan.py`, `src/aeat/application/workflow/_profile_health.py`, and related tests.
- Hygiene guardrail files: `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`, `src/aeat/tests/secure_sql.py`, and `src/aeat/tests/test_secure_sql.py`.
- Locale files: `src/aeat/locales/ca.yml`, `en.yml`, `es.yml`, and `hu.yml`; these remain governed by the locale CLI mandate if touched again.
- Secure-storage vault artifacts: the secure-storage ADR, architecture research, API audit, production hardening plan, W01 review, W01 exec records, and this W09 execution trail.
- Adjacent testimonial artifacts: fresh persona audit, findings inventory, repair plan, testimonial wave plan, and capability-gap research. These are adopted only through `W08`.

The open technical rows that cover these artifacts are `W02.P03.S11-S14`, `W02.P04.S15-S19`, `W03.P05-S06`, `W04.P07-S08`, `W05`, `W06`, `W07`, and `W08`. Existing dirty storage runtime files do not close `W02.P03.S11`; that row still requires focused implementation review, step record, tests, and plan state transition.

## Tests

Validated with `git status --short` plus focused `rg` filters for storage, secure-object, fresh-persona, route-guard, repair, custody, runtime, locale, and hygiene paths.
