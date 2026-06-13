---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `secure-storage-production-hardening` Critical Error Triage

GATE-001 | CRITICAL | Fixed stale master-key smoke test contract after fail-closed provisioning hardening.

`test_master_key_persists_across_provider_instances` still called `FileFallbackMasterKeyProvider.get_master_key()` on an unprovisioned store. The provider now correctly refuses that path with `MasterKeyMaterialMissingError`; explicit enrollment must mint key material through `provision_master_key()`.

Resolution: changed the smoke test to provision the file-fallback master key explicitly, then verify a second provider instance can recover the same key using the same passphrase. This preserves the production invariant that ordinary reads never implicitly create master-key material.

Verification:

- `uv run ruff check src/aeat/adapters/persistence/storage/test_substrate_smoke.py`
- `uv run pytest -q src/aeat/adapters/persistence/storage/test_substrate_smoke.py`
- `uv run ruff check src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/test_substrate_smoke.py`
- `uv run pytest -q src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/test_substrate_smoke.py`
