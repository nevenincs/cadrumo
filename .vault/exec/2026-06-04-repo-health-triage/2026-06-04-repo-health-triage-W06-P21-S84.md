---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S84'
related:
  - "[[2026-06-04-repo-health-triage-plan]]"
  - "[[2026-07-03-repo-health-triage-audit]]"
---

# Run full quality-audit and persist final diagnostic matrix

## Scope

- `.vault/audit`

## Description

- Rerun the full quality-audit surface (the `audit-*` lane family plus the composed `dev.audit.report` verdict) against committed HEAD, capturing full logs to disk.
- Extract the final red/amber/green diagnostic matrix and the production complexity, dead-code, and duplication findings from the on-disk logs.
- Reverify the campaign's own W06.P19 complexity deliverables against the current tree.
- Persist the final diagnostic matrix, owner-deliverable verification, and per-red owner attribution to the 2026-07-03 repo-health-triage diagnostic audit.

## Outcome

The final quality-audit matrix is: shadowing AMBER (one grandfathered symbol), duplication AMBER (71 clones, 0.49%), layering RED (peer import-linter break), complexity RED (267 new/regressed hotspots, all peer-created split modules), dead-code 4 peer findings, dependency drift GREEN; overall RED. Every RED and AMBER dimension is peer-owned; none is an owner file. The campaign's complexity deliverables still hold below threshold (`build_wizard_command` cognitive 3, `initial_values` cognitive 2), and the S79 dependency-drift-green result persists. The full matrix, owner-deliverable verification, and per-red owner attribution are recorded in the 2026-07-03 repo-health-triage audit; that audit is the artifact for this step, co-carried with the W06.P21.S83 hard-gate evidence because the live CLI mints one audit per feature per date.

## Notes

- The retired `just quality-audit` umbrella recipe is now the `audit-*` lane family plus `dev.audit.report`; the current-surface equivalents were run and named in the audit.
- `dev.audit.complexity` is now baseline-driven (267 new/regressed, 210 baselined, 23 resolved); no baseline was written, so peer complexity debt is disclosed, not absorbed under this campaign.
- `complexipy` required `PYTHONUTF8=1` to avoid a Windows cp1252 `UnicodeEncodeError` on its glyph output.
