---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S28'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Split residual M200 export fragments below pressure ceiling

## Scope

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export`

## Description

- Check the M200 export directory for local diff before changing registry data.
- Measure current export fragment pressure after the earlier page-019 split.
- Split the ten remaining export fragments at or above the 1,200-line pressure
  band into ordered `.part-001.toml` and `.part-002.toml` fragments.
- Preserve field-block order by splitting only at
  `export_layouts.records.fields` table boundaries.
- Repeat only the layout id and record id in second fragments, matching the
  generic directory-mode merge contract.
- Verify original field id sequence against the concatenated split parts.
- Run focused directory-mode, reviewability, and committed-registry tests.

## Outcome

- The ten residual high-pressure M200 export fragments were replaced with
  twenty ordered fragments.
- The largest file in the M200 export directory is now 885 lines.
- No M200 export row exceeds the 600-character focused row gate.
- Field id order was preserved for all ten split records:
  115, 113, 111, 105, 105, 102, 97, 93, 92, and 88 fields respectively.
- Focused tests passed:
  `test_directory_mode_merges_export_record_field_fragments_by_record_id`,
  `test_committed_registry_toml_files_stay_reviewable`,
  `test_registry_toml_fragments_stay_reviewable`,
  `test_registry_reviewability_baseline_remains_well_below_hard_cap`, and
  all of `test_committed_registry.py`.

## Notes

- The first mechanical split pass used an over-escaped field-header regex and
  left the field run effectively in `.part-002.toml`. The line-count output
  exposed the issue immediately. The generated `.part-002.toml` files still
  contained the full original field sequence, so the split was repaired from
  those files before tests or staging.
- A first field-order parity check also counted duplicated record ids. The
  matcher was corrected to count only ids directly following
  `export_layouts.records.fields` headers; the corrected parity check passed.
