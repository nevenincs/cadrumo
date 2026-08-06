---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:797ed5cf7cdf1d75097ceb4cf8d0ab82bcf6a5e147214f4d34965cc3f00f4e01'
step_id: 'S31'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Correct the withheld-maternidad advisory

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/locales/`

## Description

- Remove the claim that the deduction reaches only a descendant under three, which a later Step falsified by adding the date-scoped adopcion window.
- State both limbs, so the message describes the law the engine now applies.
- Name the entry-date route as the remedy instead of the birth date.

## Outcome

The false claim is gone from the shipped message and the advisory now names the inscripcion and acogimiento entry dates. Verified at HEAD rather than from the report: the old sentence returns no hits, and the entry-date route is present.

The remedy change is the substantive half. For the exact population the window added -- an over-three adoptee with no entry date recorded -- the real gap is a missing entry date, and the previous message instead invited the operator to correct the birth date. On a filing input that is guidance toward a false declaration: it steers a filer toward altering a fact in order to make a figure land.

The reasoning is recorded at the message itself rather than only in this record, so a later author who finds the birth date a tempting thing to name meets the argument against it at the point of change.

## Notes

The change landed inside an automated checkpoint sweep rather than under the implementing agent's own commit. The agent verified the swept content was byte-identical to its edit before treating the Step as landed, and confirmed the attribution with a content search rather than assuming it. The commit subject carrying the change is `fix(modelo): land the withheld-advisory message its test already asserts`.

The accompanying structural regression test asserts that the message names the entry-date facts and no longer carries the false claim. It asserts structure rather than rendered prose, so it does not break when the copy is translated or reworded.
