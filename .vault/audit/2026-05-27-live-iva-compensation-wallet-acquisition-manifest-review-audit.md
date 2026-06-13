---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-27-live-iva-compensation-wallet-w07-p17-s60-acquisition-manifest-exec]]'
  - '[[2026-05-27-live-iva-compensation-wallet-w07-p17-s61-acquisition-manifest-reload-exec]]'
---

# `live-iva-compensation-wallet` Code Review

LIVEIVA-MANIFEST-001 | MEDIUM | RESOLVED | Manifest persistence could bypass the required active-profile runtime

The first implementation default-constructed the acquisition-manifest repository
through the generic secure-bound repository route. That route can fall back to
process-default storage when no active bucket is selected, which did not satisfy
the plan requirement that live remote-state acquisition manifests persist through
active-profile `StorageRuntime` repositories. The repository now imports the
public secure-bound base and default-constructs with
`secure_object_repository_for_active_bucket`; a sessionless-storage regression
test proves persistence raises `StorageValidationError` without an active
profile runtime.

LIVEIVA-MANIFEST-002 | MEDIUM | RESOLVED | Persisted manifest stored local output path metadata

The first manifest model copied `output_root` from the report into encrypted
storage. Even encrypted/reloadable diagnostics should avoid local operator path
metadata because reload/list APIs can surface profile labels, usernames, or
private workspace structure. The manifest no longer has an `output_root` field,
and the roundtrip test verifies the private output-root marker is absent from
the model JSON and database bytes.

LIVEIVA-MANIFEST-003 | LOW | RESOLVED | Namespace object-key grammar did not match digest derivation

The first implementation truncated the acquisition id digest while the central
namespace grammar described a SHA-256 manifest hash. The object key now uses the
full SHA-256 digest over the redacted manifest seed, and the registry grammar
names that seed explicitly.

## Verification

- `uv run pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_runtime.py` passed.
- `uv run ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py` passed.

LIVEIVA-MANIFEST-004 | INFO | REVIEWED | Stored evidence report reloads acquisition summaries without raw ids

Follow-up review found no issues in the `load_iva_remote_state` acquisition
summary extension. The stored evidence report now reads stored manifests only,
hashes the acquisition object key before surfacing it, and exposes no local path
or taxpayer identifier fields. Focused pytest and ruff gates passed for the
reload extension.
