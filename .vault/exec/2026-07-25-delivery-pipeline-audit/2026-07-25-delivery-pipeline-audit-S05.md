---
tags:
  - '#exec'
  - '#delivery-pipeline-audit'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:a82fb4d64ee6587f384519ba24a5d56743a265e6c4f0952e0c71fc815e5eb69a'
step_id: 'S05'
related:
  - "[[2026-07-25-delivery-pipeline-audit-plan]]"
---

# D3, raise the two companion pyprojects from Development Status 3 Alpha to 4 Beta so one cohort carries one posture

## Scope

- `packaging/cadrumo_data_manuals/pyproject.toml`
- `packaging/cadrumo_data_official/pyproject.toml`

## Description

Verify that the two data-companion distributions carry the root's development-status posture.

- Read the `Development Status` classifier from all three cohort pyprojects.
- Confirm the change is committed rather than resident only in the working tree.

## Outcome

Complete at HEAD. All three cohort distributions declare `Development Status :: 4 - Beta`. The companions moved from `3 - Alpha` in commit `ce792a1565`, subject `chore(packaging): align data-companion dev-status to the cohort Beta posture`. The root's Beta claim was already the current posture and is unchanged, per the ruling that the root's claim postdates the promotion machinery.

One cohort now carries one posture, which is the precondition the companion gate step enforces.

## Notes

No divergence remains for the gate to catch at HEAD, which is why the gate's discriminating power had to be proven against the historical divergent state rather than against the current tree.
