---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S291'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S291 - Close AFR-189 for corpus manifest

Scope: close `AFR-189` for `src/aeat/core/corpus_manifest/__init__.py` with
signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited the corpus manifest models, SHA-256 walker, atomic JSON save path, loader,
  self-attesting digest check, and drift assertion.
- Confirmed corpus manifests are plaintext JSON by design for CORPUS-class reference
  material: the sidecar provides integrity tracking, not secrecy.
- Confirmed the module does not resolve active profiles, open secure-object
  repositories, derive SQL routes, access master-key material, or call remote
  providers.
- Confirmed malformed/tampered/drifted manifests raise typed AEAT errors registered
  in the central error registry and localized in all audited locales.
- Repaired the intersecting sensitive-persistence write inventory after docs/API-doc
  generator refactoring changed the observed call names.
- Ran focused ruff, real corpus-manifest behavior tests, sensitive-persistence policy
  tests, docs API stub tests, locale audit, and vaultspec RAG search.

## Outcome

`AFR-189` is closed as a retained plaintext integrity sidecar boundary. The corpus
manifest surface remains outside runtime secure bucket management; runtime enrollment
continues to live in storage runtime factories and bucket/session guards. Plaintext
file writes for this module are covered by the sensitive-persistence reviewed-write
inventory.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/corpus_manifest/__init__.py src/aeat/core/corpus_manifest/_errors.py src/aeat/core/corpus_manifest/test_manifest.py src/aeat/core/errors/registry/_core.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- `uv run --no-sync pytest -q src/aeat/core/corpus_manifest/test_manifest.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- `uv run --no-sync pytest -q -m docs src/aeat/tests/test_docs_api_stubs.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "corpus manifest plaintext JSON sha256 tamper drift atomic save no secure bucket repository" --type code --port 8766 --max-results 8`

## Notes

The first sensitive-policy run used a stale single-test selector and collected no
tests. The full policy file was then run and initially exposed documentation-generator
inventory drift unrelated to corpus manifest secrecy; that drift was fixed and the
full policy file now passes.
