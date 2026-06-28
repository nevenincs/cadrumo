---
step_id: "S01"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W01.P01.S01 step record

## Step

Add worker_class fact enum with value trabajador_del_mar to the user profile schema TOML.

## Files Touched

- `src/aeat/_data/registry/aeat/user_profile/schema.toml` — added `maritime_worker` section with `worker_class` enum field.

## Commit

`7d7a9e7f0` — feat(maritime-worker): add maritime_worker profile section (S01+S02)

## BOE Citations

- Ley 35/2006 Art. 7.p) BOE-A-2006-20764 — primary foreign-work exemption
- Ley 19/1994 Arts. 73.2 73.3 75.1 75.3 BOE-A-1994-16100 — REBECA 50% exemption
- Ley 35/2006 DA 41 BOE-A-2006-20764 — DA 41 inactive binding anchor
- Ley 6/2018 BOE-A-2018-9268 — DA 41 enabling amendment
- Ley 47/2015 BOE-A-2015-11346 — RETMAR mandatory filing

## Outcome

worker_class enum field added with schedule_predicates and full legal_refs. Schema validates and all existing user_profile tests continue to pass.
