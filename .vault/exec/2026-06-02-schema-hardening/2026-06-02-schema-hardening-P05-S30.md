---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S30'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Re-run corpus fragment headroom audit after residual pressure splits

## Scope

- `.vault/audit`

## Description

- Measure all committed AEAT modelo TOML file line counts.
- Measure all committed AEAT modelo TOML maximum row widths.
- Record threshold counts and modelo pressure map after S28 and S29.
- Identify the next pressure substrate for future registry-hardening work.
- Run focused registry reviewability tests.
- Run vault checks and close P05.S30 through the vault plan CLI.

## Outcome

- No TOML file exceeds the hard 1,750-line gate.
- No TOML row exceeds the 600-character focused row gate.
- No TOML file remains above 1,500 lines.
- Only one TOML file remains above 1,200 lines:
  `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-002.toml`
  at 1,465 lines.
- The next substrate is M200 records constructs, not M200 export or M303.
- Focused reviewability tests passed:
  `test_committed_registry_toml_files_stay_reviewable`,
  `test_registry_toml_fragments_stay_reviewable`, and
  `test_registry_reviewability_baseline_remains_well_below_hard_cap`.
- Vault checks passed for `registry-fragment-headroom-post-splits`; the parent
  schema-hardening checks retained only older annotation warnings outside this
  step.

## Notes

- This step is audit-only and made no registry data or code edits.
