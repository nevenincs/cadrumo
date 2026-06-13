---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S376]]'
---

# `secure-storage-production-hardening` Code Review

## S376-001 | PASS | Bootstrap registry stays sessionless

`_bootstrap_exempt.py` is a typed verb-path registry plus prefix matcher. It has no direct storage construction, master-key provider acquisition, environment access, or settings access. Bare invocation and whitespace-only paths remain exempt for metadata/help surfaces.

Evidence:
- `src/aeat/entrypoints/cli/_bootstrap_exempt.py:35`
- `src/aeat/entrypoints/cli/_bootstrap_exempt.py:57`
- `src/aeat/entrypoints/cli/_bootstrap_exempt.py:82`
- `src/aeat/entrypoints/cli/_bootstrap_exempt.py:87`

## S376-002 | PASS | Root callback evaluates policy before master-key acquisition

The CLI root active-bucket gate resolves bootstrap exemption and calls centralized storage write policy before opening the master-key provider. The master-key provider is acquired only after the no-active-profile, existing-session, and bootstrap-exempt returns, so exempt recovery/on-ramp verbs do not require an active bucket session.

Evidence:
- `src/aeat/entrypoints/cli/__init__.py:310`
- `src/aeat/entrypoints/cli/__init__.py:347`
- `src/aeat/entrypoints/cli/__init__.py:348`
- `src/aeat/entrypoints/cli/__init__.py:360`
- `src/aeat/entrypoints/cli/__init__.py:365`

## S376-003 | PASS | Runtime write policy is centralized and settings-backed

`inspect_storage_write_policy` accepts the bootstrap-exempt decision from the CLI gate, short-circuits exempt verbs before route classification, and otherwise classifies profile-bound writes through `classify_storage_route`. Root fallback and explicit database routes are refused with translated boundary message keys.

Evidence:
- `src/aeat/application/storage_write_policy.py:10`
- `src/aeat/application/storage_write_policy.py:118`
- `src/aeat/application/storage_write_policy.py:129`
- `src/aeat/application/storage_write_policy.py:151`
- `src/aeat/application/storage_write_policy.py:155`
- `src/aeat/application/storage_write_policy.py:164`
- `src/aeat/application/storage_write_policy.py:173`

## S376-004 | PASS | Real-behavior tests cover cold-root and route-policy contracts

The repair bootstrap tests invoke actual CLI verbs against a pristine storage root and assert clean sessionless execution without `NoActiveBucketSession` crashes. The storage write-policy tests instantiate real `Settings` objects and verify root fallback refusal, explicit database refusal, active bucket allowance, bootstrap short-circuiting, and profile-bound verb classification.

Evidence:
- `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py:63`
- `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py:81`
- `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py:96`
- `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py:111`
- `src/aeat/application/test_storage_write_policy.py:19`
- `src/aeat/application/test_storage_write_policy.py:33`
- `src/aeat/application/test_storage_write_policy.py:53`
- `src/aeat/application/test_storage_write_policy.py:66`
- `src/aeat/application/test_storage_write_policy.py:105`

## S376-005 | FIXED | Reviewer found missing ledger-rule write-policy coverage

The `vaultspec-code-reviewer` persona found that `app ledger rule add` and `app ledger rule apply` were profile-bound mutation surfaces missing from `PROFILE_BOUND_WRITE_VERB_PATHS`. The finding was blocking because unknown paths fall through as `NON_PROFILE_BOUND_VERB`, bypassing the centralized root-gate write-policy refusal. The catalogue now includes both paths, and the operator-path classification test pins both.

Evidence:
- `src/aeat/application/storage_write_policy.py:62`
- `src/aeat/application/storage_write_policy.py:63`
- `src/aeat/application/test_storage_write_policy.py:98`
- `src/aeat/application/test_storage_write_policy.py:99`

## S376-006 | PASS | Validation and RAG grounding completed

Validation passed for focused lint, cold-root repair CLI coverage, storage write-policy backend coverage, and locale audit. Vaultspec RAG search confirmed the bootstrap exemption registry, root active-session gate, and storage write-policy backend as the relevant runtime orchestration surfaces.

Commands:
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_bootstrap_exempt.py src/aeat/entrypoints/cli/__init__.py src/aeat/application/storage_write_policy.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/application/test_storage_write_policy.py`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/application/test_storage_write_policy.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "bootstrap exempt CLI active bucket session gate master key runtime default storage write policy" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "ledger rule add apply storage write policy profile bound write verb root fallback active bucket" --type code --port 8766 --max-results 8`
