---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:3ba3384645086e9c53193262518cb9163472c9a7203776f669145e8f927f2118'
step_id: 'S23'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Add the Art. 81.1 post-birth alta increment

## Scope

- `src/cadrumo/core/external_constants.py`
- `src/cadrumo/domain/contribuyente/_deduccion_maternidad.py`

## Description

- Add the 150 euro increment for the month completing the thirty-day contribution period following a post-birth Social Security registration.
- Raise that child's ceiling to 1.350 euros when the increment applies, additively rather than as a replacement for the ordinary cap.
- Gate both on filing years from 2023 only.
- Add the operator-supplied per-descendant fact naming the completing month, with its round-trip, flag key and refusal on a corrupt stored value.

## Outcome

A claimant who earns the increment is no longer clipped at the ordinary 1.200 euro cap. The AEAT manual's own worked example reproduces exactly: two mellizos at eight months plus the increment give 950 each and 1.900 together, and the older child at four months gives 550.

The year gate is the part that mattered and it is proven in both directions -- a case granting the increment from 2023, and a 2022 case that never exceeds the ordinary cap. The per-hijo limit reads 1.200 in the 2020 and 2021 manuals and 1.350 only from 2023 onward, because the qualifying supuestos widened on 1 January 2023. Adopting the manual's printed 1.350 figure without scoping it would have over-granted every filing year through 2022 -- a defect of the opposite sign, backed by an accurate citation.

The ordinary cap's relationship to the monthly figure is unchanged and its contract assertion was deliberately left intact, because the increment is additive to that cap rather than a substitute for it.

## Notes

Grounded on the bundled AEAT manual rather than the per-article normative excerpt. That excerpt carries no mention of the 150 euro increment at all and is a two-vintage hybrid, tracked as its own Step and escalated for operator refresh rather than hand-authored -- authoring the missing statutory text to satisfy a corpus gate would be fabricating evidence.

Most of this Step's diff landed inside a broad checkpoint commit authored by neither the implementing agent nor the coordinator, which swept the work mid-edit; the agent committed only the residue under its own subject. The exec trail for this Step therefore points partly at a commit whose message describes none of it.

Deliberately NOT built: the interactive wizard page for the new fact. The Step did not ask for it, and the precedent from the earlier entry-surface Step is that the interactive surface is its own tracked change. The flag-driven automation contract is fully wired.

The implementing agent attempted a hunk-filtering stage against the shared index while editing the locale catalogues, corrupted the index, disclosed it, and recovered with a per-file re-add from an intact working tree. No content was lost on disk, and the recovery incidentally cleared a truncation hazard it had not caused.
