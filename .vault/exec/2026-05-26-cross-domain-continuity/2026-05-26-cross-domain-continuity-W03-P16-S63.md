---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:b03e8e64eb9c866fe1706fa8890faf5e595c019139cfb5e01b9335faea94a3dd'
step_id: 'S63'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# profile-binding-schema-audit

## Scope

- `if findings surface a profile binding declared elsewhere`
- `add it to the validation pass`
- `otherwise close S63 as confirmed-empty with a note that S62 already covers the only modelo (100) with profile bindings`
- `src/aeat/_data/registry/aeat/modelos/`

## Description

- Ran a repository-wide search for `source = "profile"` under the registered modelo bindings.
- Found current profile-sourced bindings in Modelos 036, 100, 200, 202, 210, and 303; this disproves the historical premise that only Modelo 100 used them.
- Added `W03.P16.S415` to validate each discovered modelo's selector-to-schema and resolver path before any change is credited.
- Ran the existing real-path Modelo 100 profile-binding suite: `11 passed`.

## Outcome

S63 is complete as a discovery-and-expansion step, not as a confirmed-empty audit. The broader validation remains explicitly open in S415.

## Notes

No production code changed. The former S62-S64 assumption was stale relative to the present registry surface.
