---
tags:
  - '#exec'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:88fcf0a3777879d12e9b180dfcf614d27290bba3289310788d8fb700c08cafed'
step_id: 'S03'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-plan]]"
---

# Stop the generator printing the six Primitivo line items, judging its remaining output against the printed form rather than against the profile, which reverses the causality that produced the defect

## Scope

- `dev/`
- `generator`

## Description

- Delete the generator's primitive draw block, which printed the six `Primitivo` line items.
- Delete the primitive fields from the corpus fixture dataclass and the helper that derived them.
- Regenerate all 15 synthetic corpus PDFs and their sidecars.

## Outcome

The draw block is deleted outright rather than gated behind a legacy-template branch. Gating was only required under the rejected option of re-scoping one revision; because both revisions were re-scoped together, the shared-support straddle the companion audit warned about does not arise.

The generator's remaining output was judged against the printed form rather than against the profile, which is the causality reversal this step exists to perform. The labels being removed carried a `Primitivo` prefix whose stated purpose was to avoid colliding with the form-page totals; on the real form that collision is not an accident of naming but the fact itself, since the primitive and the printed box are the same box.

## Notes

The generator's own comment recording why the prefix existed was the clearest single piece of evidence that the document had been shaped to fit the profile.
