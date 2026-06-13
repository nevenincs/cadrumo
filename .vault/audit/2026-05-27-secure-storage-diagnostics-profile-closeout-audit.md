---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
---

# Diagnostics/profile storage closeout audit

## Scope

This closeout covers W12.P26.S314, W12.P26.S315, W12.P26.S316, and W12.P26.S317.

| Row | AFR | Module | Disposition |
| --- | --- | --- | --- |
| W12.P26.S314 | AFR-212 | `diagnostics.__main__` | hardened localized diagnostics entrypoint |
| W12.P26.S315 | AFR-213 | `diagnostics.profile` | hardened target-profile storage routing |
| W12.P26.S316 | AFR-214 | `domain._secure_storage_runtime` | obsolete target absent; adapter runtime is canonical |
| W12.P26.S317 | AFR-215 | `domain.attachments._models` | accepted strict manifest model boundary |

## Findings

- `diagnostics.__main__` remains the only registration point for `python -m aeat.diagnostics`; it does not reintroduce retired operator `aeat config profile get/set/unset` or `aeat config repair list` surfaces.
- `diagnostics.secure_objects` now renders help and conflicting-filter errors through `tr()`, while storage behavior remains delegated to `build_repair_list_report`.
- `diagnostics.profile` no longer writes explicit `--profile NAME` edits through the active profile by accident. `get`, `set`, and `unset` resolve the target manifest, then open `profile_storage_session(pointer.bucket_id)` so lifecycle reads and workflow-state writes bind to the named bucket.
- The profile diagnostics tests are real Typer and real encrypted profile-bucket tests. The regression tests seed two profile buckets, make one active, then prove explicit `--profile named` reads/writes the named bucket without mutating the active bucket.
- `src/aeat/domain/_secure_storage_runtime.py` is absent by design. The prior W12.P21.S84 review records deletion of the domain helper; current runtime repository construction lives at the adapter-owned `runtime_repository` boundary.
- `domain.attachments._models` is a strict frozen pydantic manifest boundary. It enforces digest shape, content-address identity, timezone-aware capture timestamps, immutable metadata, and bucket ownership fields. Attachment persistence is covered by encrypted SQL roundtrip tests; the model file itself does not write plaintext state or create a parallel manifest store.

## Validation

- `uv run ruff check src/aeat/diagnostics/__main__.py src/aeat/diagnostics/secure_objects.py src/aeat/diagnostics/profile.py src/aeat/diagnostics/test_secure_objects.py src/aeat/diagnostics/test_profile.py src/aeat/entrypoints/cli/test_config_setter.py`
- `uv run pytest src/aeat/diagnostics/test_secure_objects.py src/aeat/diagnostics/test_profile.py src/aeat/entrypoints/cli/test_config_setter.py -q`
- `uv run python -m aeat.locales audit`
