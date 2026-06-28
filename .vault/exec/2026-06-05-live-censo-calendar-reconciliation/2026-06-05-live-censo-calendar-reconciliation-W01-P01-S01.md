---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S01'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W01.P01.S01 - censo/profile taxpayer fact derivation

## Scope

Implemented the censo-to-taxpayer-model bridge in `src/aeat/application/user_profile/_censo_sync.py`.

## Changes

- Added `CENSO_DERIVED_SOURCE_TAG = "aeat_censo_derived"` to separate direct AEAT censo facts from facts derived from the combination of censo and profile evidence.
- `apply_censo_to_profile` now preserves operator-entered facts, replaces prior censo/direct-derived facts, writes fresh direct censo facts, and adds derived facts only when no retained profile fact already owns the path.
- Added conservative derivation rules:
  - DNI/NIE-shaped profile identity derives `taxpayer_type.entity_type = natural_person`.
  - A non-empty censo `activities.iae_epigraph` derives `taxpayer_type.irpf_income_categories = actividad_economica`.
- Deliberately did not infer IRPF estimation regime, legal entity subtype, ROI/OSS/SII/REDEME, withholding obligations, large-company status, or other obligations not evidenced by the current G313 snapshot/profile bridge.
- Exposed derived paths through `CensoApplyResult.derived_paths`.

## Result

The profile projection can now become calendar-eligible from live censo evidence when censo supplies IAE activity and the profile supplies DNI/NIE identity plus the remaining declared axes. Missing censo activity evidence remains a refusal path, not a silent obligation inference.
