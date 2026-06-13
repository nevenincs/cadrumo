---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# `schema-hardening` `P05` summary

Phase P05 closed the residual registry fragment pressure identified during the
initial headroom audit.

- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export`
- Modified: `src/aeat/_data/registry/aeat/modelos/303`
- Modified: `.vault/plan/2026-06-02-registry-hardening-next-work-plan.md`
- Created: `.vault/audit/2026-06-02-registry-m200-export-fragments-code-review-audit.md`
- Created: `.vault/audit/2026-06-02-registry-m303-fragments-code-review-audit.md`
- Created: `.vault/audit/2026-06-02-registry-fragment-headroom-post-splits-audit.md`
- Created: `.vault/audit/2026-06-02-registry-fragment-headroom-post-splits-code-review-audit.md`
- Created: `.vault/exec/2026-06-02-schema-hardening/2026-06-02-schema-hardening-P05-S28.md`
- Created: `.vault/exec/2026-06-02-schema-hardening/2026-06-02-schema-hardening-P05-S29.md`
- Created: `.vault/exec/2026-06-02-schema-hardening/2026-06-02-schema-hardening-P05-S30.md`

## Description

- S28 split ten residual M200 export fragments above the 1,200-line pressure
  band into ordered field fragments.
- S29 split M303 casilla and export pressure files into generic table-array,
  field, and record fragments.
- S30 re-ran corpus headroom measurements and found no TOML file above 1,500
  lines, one TOML file above 1,200 lines, and no row above 600 characters.
- The next registry-size substrate is M200
  `records/constructs.part-002.toml`; M200 export and M303 are no longer the
  next pressure targets.

## Verification

- `test_directory_mode_merges_export_record_field_fragments_by_record_id`
  passed during S28 and S29.
- `test_committed_registry_toml_files_stay_reviewable` passed during S28, S29,
  and S30.
- `test_registry_toml_fragments_stay_reviewable` and
  `test_registry_reviewability_baseline_remains_well_below_hard_cap` passed
  during S28, S29, and S30.
- `test_committed_registry.py` passed during S28 and S29.
- `test_modelo_303_registry.py` passed during S29.
- Vault feature checks passed for `registry-m200-export-fragments`,
  `registry-m303-fragments`, and `registry-fragment-headroom-post-splits`.
