---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:bf0e9303af5c11b4dd25b5018b2aeb265b04ec4df23324884c89d7b5592ed227'
step_id: 'S26'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# record approved follow-up UX issues

## Scope

- `.vault/exec/2026-06-04-docs-sphinx-ux`

## Description

- Collect every follow-up UX issue surfaced by the operator's approved
  review of the consolidated packet (brand, navigation, rendered
  experience) and record its disposition.

## Outcome

- The operator's single change request from the review — the generated CLI
  reference read as an unstructured command dump and should be separated by
  major verb group, each group opening with the real verb help output — was
  implemented inside this plan under the reference feedback-incorporation
  Step (generator restructure in `dev/docs/cli_reference.py`, per-group
  pages, canonical group ordering, captured help blocks; all reference and
  build gates green).
- No residual UX follow-up issues remain from the approved review: brand,
  route navigation, and the rendered desktop and mobile experience were
  approved without changes, and the two defects found during the rendered
  inspection (header-nav API retarget, IRPF lifecycle profile-create flag)
  were fixed before closure.
- With this record the plan's Step set is complete.

## Notes

- One non-UX housekeeping observation from the same session is tracked
  outside this plan: the example environment file still lists retired
  former-product variable names that the settings layer now deliberately
  ignores; that is a rename-residue cleanup, not a documentation UX issue.
