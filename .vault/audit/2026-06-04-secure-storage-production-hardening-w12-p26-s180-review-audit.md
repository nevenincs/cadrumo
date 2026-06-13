---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S180]]'
---

# `secure-storage-production-hardening` `W12.P26.S180` Review

## S180-001 | PASS | Duplicate guard retired

`test_no_classvar_state.py` and `test_master_key_no_classvars.py` both parsed `_master_key.py` to enforce that `KeyringMasterKeyProvider` and `FileFallbackMasterKeyProvider` do not declare `ClassVar` state. Keeping both was redundant coverage, not stronger architecture enforcement. The duplicate file is removed.

## S180-002 | PASS | Canonical invariant remains enforced

`test_master_key_no_classvars.py` remains as the canonical guard. It covers both guarded provider classes in one AST walk and reports provider/line/target details for any future `ClassVar` regression.

## S180-003 | PASS | Plan classification is honest

`AFR-078` is reclassified from `bootstrap-custody` to `retired`, because the affected file is a duplicate test guard rather than an implementation surface. The plan row text now records the retirement instead of implying production hardening work landed in that deleted file.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_master_key_no_classvars.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py` passed with 14 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/test_master_key_no_classvars.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with only the known `PLAN022` ordering warning.

Review-agent note: spawning `vaultspec-code-reviewer` remains unavailable in this session due the agent thread limit, so the supervisor completed the same checklist locally.

Disposition: close `AFR-078` as retired duplicate.
