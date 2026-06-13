---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S02'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P01.S02`

Added first-class output redaction policy names without expanding the persisted sensitivity enum.

- Modified: `src/aeat/core/classification/__init__.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P01-S02.md`

## Description

The classification module now defines `OutputSensitivityClass`, `OutputClassificationPolicy`, `default_output_policy_for`, and `default_output_policy_table`. CLI public output is represented as an emit-only surface with `persisted_as=None`, while diagnostic output remains explicitly associated with `SensitivityClass.DIAGNOSTIC`.

The shared audit-shaped redaction rule tuple is factored into `_AUDIT_REDACTION_RULES` and reused by audit, diagnostic, and output policies without changing existing persisted sensitivity classes.

## Tests

- `uv run ruff check src/aeat/core/classification/__init__.py`
- `uv run python -c "from aeat.core.classification import OutputSensitivityClass, SensitivityClass, default_output_policy_for, default_policy_for; ..."`
- `uv run pytest -q src/aeat/adapters/persistence/storage/blob_store/test_blob_store.py::TestCiphertextSensitiveBlobs::test_round_trip`
- `uv run pytest -q src/aeat/adapters/persistence/storage/test_substrate_smoke.py src/aeat/adapters/persistence/storage/blob_store/test_blob_store.py::TestCiphertextSensitiveBlobs::test_round_trip` failed in `test_master_key_persists_across_provider_instances` with `MasterKeyMaterialMissingError` for an unprovisioned file-fallback master key directory before the new output classification policy is exercised.
