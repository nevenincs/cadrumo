---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S22'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W03.P05.S22`

Registered the remaining auth, session, cache, diagnostic, remote-facing, and Sede observation secure-object namespace contracts already written through `SecureObjectRepository`.

- Modified: `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- Modified: `.vault/audit/2026-05-27-secure-storage-hierarchy-namespace-inventory.md`

## Description

This step adds central namespace definitions for the production secure-object writes used by AEAT browser sessions, Clave Movil diagnostics, Google OAuth client and token records, Google OAuth metadata, Google Drive configuration, LLM cache and usage telemetry, filed-declaration artefacts and observations, and IVA-wallet observation captures.

Each registered namespace records the owner module family, sensitivity class, schema version, scope, and object-key grammar currently used by the production call sites. The storage package exports the new definitions so W03.P05.S23 can replace local literals without importing registry internals.

Outbound storage-provider `_probe` namespaces were deliberately not enrolled here. Those provider sentinel paths are not encrypted SQL secure-object namespaces and remain tracked by the remote-mirror/provider-store follow-up waves.

## Tests

Passed:

- `uv run ruff check src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py .vault/audit/2026-05-27-secure-storage-hierarchy-namespace-inventory.md`
- `uv run pytest -q src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py src/aeat/adapters/outbound/google/test_session_store_roundtrip.py src/aeat/adapters/outbound/llm/test_cache_roundtrip.py src/aeat/adapters/outbound/llm/test_usage_roundtrip.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/auth/test_diagnostics.py`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
