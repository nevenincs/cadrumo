---
step_id: "S02"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W01.P01.S02 step record

## Step

Add vessel_flag, waters_type, vessel_registry, and retmar_registered supporting facts to the user profile schema TOML.

## Files Touched

- `src/aeat/_data/registry/aeat/user_profile/schema.toml` — added vessel_flag, waters_type, vessel_registry, retmar_registered fields to the maritime_worker section.

## Commit

`7d7a9e7f0` — feat(maritime-worker): add maritime_worker profile section (S01+S02)

S01 and S02 committed together as they modify the same section of the same file and the test suite validates the combined state.

## BOE Citations

- vessel_flag: Ley 35/2006 Art. 7.p) BOE-A-2006-20764 — flag-state condition for Art. 7.p) eligibility
- waters_type: Ley 35/2006 Art. 7.p) BOE-A-2006-20764 — international waters qualification
- vessel_registry: Ley 19/1994 Arts. 73.2 73.3 75.1 75.3 BOE-A-1994-16100 — REBECA register classification
- retmar_registered: Ley 47/2015 BOE-A-2015-11346 — mandatory filing obligation since January 2023

## Outcome

All four supporting facts added with correct types (enum/boolean), effective_dated=true, and legal_refs. Schedule predicates on worker_class and retmar_registered for filing obligation routing. Schema validates and all 28 user_profile tests pass.
