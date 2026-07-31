---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:cbdc6b487fcbeacc90b62da817cbd7447c0e711b99b4fd37cd7352222fe161a0'
step_id: 'S02'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Populate completeness_manifest in _subview_from_snapshot from snapshot.revision.completeness_manifest

## Scope

- `src/aeat/application/filing/runtime.py`

## Description

- Populate `completeness_manifest=snapshot.revision.completeness_manifest` in `_subview_from_snapshot`, alongside the existing `export_layouts` projection, so the render choke point reaches the manifest without a second authority load.

## Outcome

Landed in commit `807a55eb9`. The subview is projected with the revision's manifest verbatim (identity confirmed by the S03 roundtrip test).

## Notes

Confirmed `_subview_from_snapshot` is the only `RegistryModeloSubview` construction site, so the new required field breaks no other caller.
