---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S246]]'
---

# `secure-storage-production-hardening` `W12.P26.S246` Review

## S246-001 | PASS | Registry corpus access is a plaintext exception

`registry/_corpus.py` reads configured manual roots, bundled topic resources, and normative/manual corpus files through centralized settings and domain loaders. It does not write corpus state, profile state, secure objects, master-key material, or remote provider mirrors.

## S246-002 | FIXED | Registry corpus refusals use localized application errors

The topic locale, manual section, manual id, and manual rule-kind refusal paths now raise `RegistryApplicationInputError` with `translated_message` keys and structured context. Tests assert the durable key/context contract instead of raw English message substrings.

## S246-003 | PASS | Exceptions derive from the core application hierarchy

The module continues to raise `RegistryApplicationInputError`, which derives from `RegistryApplicationError` and the core `AeatError` base. No bare `Exception` or non-core operator-facing exception was added.

## S246-004 | PASS | Exception handling is logged at the boundary

Corpus lookup and refusal paths either raise directly or log structured warning/debug records before continuing or re-raising. The existing broad citation lookup boundary logs `exc_info=True` and re-raises; no silent swallowing was introduced.

## S246-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/registry/_corpus.py src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py` passed with 33 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-144` as `plaintext-exception`.
