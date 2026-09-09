---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1e4cffc1da3b077b0458fd626672b57c2c4d7f0f0d4b11b7242784d6f3355a4f'
step_id: 'S269'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Withdraw the writerless transcription-cache feature atomically: remove its cache-backed consent re-derivation surface, storage composition and namespace, facade/self-tests, amend the contradicted ingestion ADR, preserve consent-history enumeration, run focused consent/storage/CLI gates, and remeasure exact reachability.

## Scope

- `writerless extracted-document transcription cache`
- `cache-backed consent re-derivation command`
- `storage namespace and adapter`
- `self-tests`
- `governing ADR`

## Changes

- `D` `src/cadrumo/application/ledger/extracted_document_cache.py`
- `D` `src/cadrumo/adapters/persistence/profile/extracted_document_cache.py`
- `D` `src/cadrumo/application/ledger/tests/test_extracted_document_cache.py`
- `M` `src/cadrumo/application/ledger/consent_withdrawal.py`
- `M` `src/cadrumo/application/ledger/document_transcription.py`
- `M` `src/cadrumo/application/ledger/evidence_textlayer.py`
- `M` `src/cadrumo/application/ledger/preconditions.py`
- `M` `src/cadrumo/application/ledger/tests/test_consent_withdrawal.py`
- `M` `src/cadrumo/application/ledger/tests/test_document_transcription.py`
- `M` `src/cadrumo/application/ledger/tests/test_document_transcription_textlayer.py`
- `M` `src/cadrumo/entrypoints/adapter_composition.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_evidence_followup_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_evidence_consent_cli.py`
- `M` `src/cadrumo/entrypoints/cli/ledger_business_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_evidence_consent_cli.py`
- `M` `src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py`
- `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `M` `src/cadrumo/core/errors/registry/_domain_part1.py`
- `M` `src/cadrumo/conftest.py`
- `M` `src/cadrumo/llm/evidence_draft_vision.py`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `.vault/adr/2026-08-07-unstructured-document-ingestion-operations-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check <focused cache/consent/storage files>` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 <focused consent/transcription/namespace tests>` -> `fail`
- `verify:` `uv run --no-sync pytest -q -n0 -m integration src/cadrumo/entrypoints/cli/tests/test_evidence_consent_cli.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.locales audit` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

All 71 focused consent/transcription tests passed; the namespace suite's sole failure names five unrelated peer-owned namespaces and not the withdrawn cache. All 8 real CLI consent-list tests passed. Locale audit retains one missing and twelve extra peer-owned leaves after removal of the cache and stale repair-list leaves. Exact shipped modules decreased from 2061 to 2059 and unused symbols from 275 to 274; 31 unreachable modules and zero orphaned tests remain.
