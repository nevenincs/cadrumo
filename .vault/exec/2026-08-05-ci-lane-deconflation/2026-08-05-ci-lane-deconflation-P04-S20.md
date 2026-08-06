---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:0a2d7b5de090569b244c4933b2683dfb79bb91999d75dd9c21452b9364b44195'
step_id: 'S20'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Resolve the import-hygiene test-debt failures from the maternidad private reaches, raising a baseline designed to only decrease would invert the ratchet so establish whether the debt is legitimate before admitting it

## Scope

- `src/cadrumo/tests/test_import_hygiene_gate.py`

## Description

- Establish whether the import-hygiene test debt is legitimate before admitting it to the baseline.
- Route the offending reaches onto the facades that own them.

## Outcome

Landed as `dd9e6b3504` ("fix(imports): route two test reaches onto the facades that own them"),
three files, 4 insertions and 3 deletions.

**The row asks a judgement question before it asks for a fix**, and the landed change is that
judgement's answer: the debt was not legitimate. Raising a baseline designed only to decrease
would have inverted the ratchet, so the reaches were repointed at the owning facades and the
baseline was left untouched. A three-file, seven-line change is the right size for that answer;
the alternative would have been a one-line baseline bump.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_import_hygiene_gate.py -q
    19 passed in 90.07s (0:01:30)

Nineteen tests selected and executed. No marker expression was applied to that invocation, so
nothing was deselected and the count is the whole module.

    git log --format=%H --grep="route two test reaches onto the facades" -1
    git show dd9e6b3504 --numstat
    (3 files, +4/-3)

## Notes

The row's framing generalises past this instance: a baseline that only ever decreases is a
ratchet, and admitting new debt to it inverts the mechanism rather than accommodating it. The
question "is this debt legitimate" has to be answered before the baseline is touched, because
touching the baseline is what makes the question unanswerable afterwards.

### The judgement is evidenced, not inferred from the change's shape

Asked to confirm whether the row's judgement half actually happened or only its mechanical
half, the distinguishing evidence is what the commit did NOT touch:

    git show dd9e6b3504 --numstat | grep baseline   ->  no match
    dev/import_hygiene_baseline.json at HEAD        ->  "sites": []

The baseline was never opened. What the commit did instead was promote
`resolve_maternidad_meses` into the owning package's public `__all__` and repoint the two
reaching tests at it — the resolution `service-imports-via-top-level-reexports` prescribes,
where promotion is a precondition of the consuming change rather than a follow-up.

So both halves of the row are satisfied: the debt was judged illegitimate, and the judgement is
readable from the artefact rather than only from its author. Had the debt been admitted, the
baseline's sites list would carry the two entries and the facade would be unchanged.
