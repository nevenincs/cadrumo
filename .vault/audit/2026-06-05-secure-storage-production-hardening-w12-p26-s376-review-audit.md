---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-10-03'
body_hash: 'sha256:88eef2b405276c8d817ac96ffd802d96c554c42e652b5f70c53b40ba1da7c4b1'
related: []
---

# `secure-storage-production-hardening` Code Review

## S376-001 | PASS | Bootstrap registry stays sessionless

`_bootstrap_exempt.py` is a typed verb-path registry plus prefix matcher. It has no direct storage construction, master-key provider acquisition, environment access, or settings access. Bare invocation and whitespace-only paths remain exempt for metadata/help surfaces.

Evidence:
- the retired module
- the retired module
- the retired module
- the retired module

## S376-002 | PASS | Root callback evaluates policy before master-key acquisition

The CLI root active-bucket gate resolves bootstrap exemption and calls centralized storage write policy before opening the master-key provider. The master-key provider is acquired only after the no-active-profile, existing-session, and bootstrap-exempt returns, so exempt recovery/on-ramp verbs do not require an active bucket session.

Evidence:
- the retired module
- the retired module
- the retired module
- the retired module
- the retired module

## S376-003 | PASS | Runtime write policy is centralized and settings-backed

`inspect_storage_write_policy` accepts the bootstrap-exempt decision from the CLI gate, short-circuits exempt verbs before route classification, and otherwise classifies profile-bound writes through `classify_storage_route`. Root fallback and explicit database routes are refused with translated boundary message keys.

Evidence:
- the retired module
- the retired module
- the retired module
- the retired module
- the retired module
- the retired module
- the retired module

## S376-004 | PASS | Real-behavior tests cover cold-root and route-policy contracts

The repair bootstrap tests invoke actual CLI verbs against a pristine storage root and assert clean sessionless execution without `NoActiveBucketSession` crashes. The storage write-policy tests instantiate real `Settings` objects and verify root fallback refusal, explicit database refusal, active bucket allowance, bootstrap short-circuiting, and profile-bound verb classification.

Evidence:
- the retired test
- the retired test
- the retired test
- the retired test
- the retired test
- the retired test
- the retired test
- the retired test
- the retired test

## S376-005 | FIXED | Reviewer found missing ledger-rule write-policy coverage

The `vaultspec-code-reviewer` persona found that `app ledger rule add` and `app ledger rule apply` were profile-bound mutation surfaces missing from `PROFILE_BOUND_WRITE_VERB_PATHS`. The finding was blocking because unknown paths fall through as `NON_PROFILE_BOUND_VERB`, bypassing the centralized root-gate write-policy refusal. The catalogue now includes both paths, and the operator-path classification test pins both.

Evidence:
- the retired module
- the retired module
- the retired test
- the retired test

## S376-006 | PASS | Validation and RAG grounding completed

Validation passed for focused lint, cold-root repair CLI coverage, storage write-policy backend coverage, and locale audit. Vaultspec RAG search confirmed the bootstrap exemption registry, root active-session gate, and storage write-policy backend as the relevant runtime orchestration surfaces.

Commands:
- the historical check
- the historical check
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "bootstrap exempt CLI active bucket session gate master key runtime default storage write policy" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "ledger rule add apply storage write policy profile bound write verb root fallback active bucket" --type code --port 8766 --max-results 8`
