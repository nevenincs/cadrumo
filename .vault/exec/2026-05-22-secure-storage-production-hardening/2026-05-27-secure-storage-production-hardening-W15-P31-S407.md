---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S407'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P31.S407`

Hardened repair diagnostics so active profile identifiers and natural object-key hints are not emitted by repair output.

- Modified: `src/aeat/application/diagnostics.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`

## Description

`config repair` previously serialized and rendered the active bucket UUID through the wizard status projection and profile-storage diagnostic summary. The repair report now redacts that repair-only projection to the stable token `active_profile`.

`config repair logs` now redacts diagnostic log tail lines before echoing them to operators. The redactor removes UUIDs, Spanish tax-id canaries, and generic keyed object-key assignments such as `object_key=...` and `lookup-key:...` from both text and JSON output.

The repair list contract remains digest-only: it verifies that the stored HMAC lookup digest is visible while the natural object key, active bucket UUID, and payload content are not.

## Tests

Passed:

- `uv run pytest -q src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- `uv run pytest -q src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/entrypoints/cli/test_repair_policy_coverage.py`
- `uv run ruff check src/aeat/application/diagnostics.py src/aeat/application/repair_integrity.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/entrypoints/cli/test_repair_policy_coverage.py src/aeat/application/test_repair_integrity.py`
