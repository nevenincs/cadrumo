---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S03'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Roundtrip-test that the export subview carries the revision completeness manifest

## Scope

- `src/aeat/application/filing/tests/test_runtime_subview_manifest.py`

## Description

- Add `test_runtime_subview_manifest.py` with three cases: the subview from a real M130 1T/2025 snapshot carries a manifest equal to the revision's; a provider-built subview exposes a non-empty manifest; a manifest-less subview reports absence via `has_completeness_manifest()`.

## Outcome

Landed in commit `807a55eb9`. Three tests pass (17s); the 254-test filing suite still collects; `ruff` clean.

## Notes

The manifest-absent case is exercised at the dataclass level (constructing a subview with `completeness_manifest=None`) rather than sourcing a manifest-less registry modelo, giving a deterministic unit assertion of the accessor contract.
