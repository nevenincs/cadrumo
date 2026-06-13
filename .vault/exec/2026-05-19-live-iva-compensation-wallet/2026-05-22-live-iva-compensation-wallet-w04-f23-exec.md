---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W04.F23'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-code-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-persona-testimonials-audit]]'
---

# `live-iva-compensation-wallet` `W04.F23`

Kept profile listing usable when legacy bucket manifests are malformed.

- Modified: `src/aeat/application/workflow/_profile_bucket_scan.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`

## Description

The config-domain persona pass found that `aeat config profile status` and `aeat config profile show` could inspect the active profile, but `aeat config profile list` failed because one legacy bucket manifest omitted the required plaintext lifecycle `status`.

The manifest scanner now skips malformed manifests on the live profile enumeration path. That preserves fail-closed behavior: a malformed legacy bucket is not switchable by label and does not participate in live name resolution. The profile list CLI reports the count as `skipped_invalid_manifests` so the operator knows degraded buckets exist, without printing malformed manifest contents, skipped bucket identifiers, profile labels, tax ids, or key material.

No live AEAT operation was performed in this step.

## Tests

- `uv run pytest src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py::test_config_profile_list_skips_legacy_manifest_missing_status src/aeat/application/user_profile/test_profile_repository.py src/aeat/application/workflow/test_state_persistence_roundtrip.py -q --disable-warnings` completed with 18 passed.
- `uv run pytest src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py src/aeat/application/user_profile/test_profile_repository.py src/aeat/application/workflow/test_state_persistence_roundtrip.py src/aeat/application/auth/test_operator.py src/aeat/application/test_state_projection.py src/aeat/application/test_diagnostics.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q --disable-warnings` completed with 145 passed.
- `uv run ruff check src/aeat/application/workflow/_profile_bucket_scan.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py` passed.
- `uv run aeat config profile list` completed successfully and reported valid profiles plus a skipped invalid-manifest count.
