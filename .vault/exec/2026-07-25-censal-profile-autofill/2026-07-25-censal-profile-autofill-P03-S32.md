---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:c4cbba65f5bde0743c435b605e83a0bea16e029e5ef5a864d19a47338013914d'
step_id: 'S32'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# DEFERRED as a property of the authority's surface, keep the regime facts operator-entered while AEAT publishes no read-only surface carrying them, this being the one deferral no effort inside this campaign can close

## Scope

- `src/cadrumo/application/live`

## Description

- Confirm the deferral's premise against the shipped schema and the adoption set rather than against the record that asserts it.
- Confirm the three eliminated routes are still described by the decision record as eliminated on live evidence, and re-run none of them.
- State the evidence that would reopen this, so the deferral is triggered rather than revisited.

## Outcome

Confirmed against the code: the reasoning still matches, and the row closes as a permanent evidence-triggered deferral.

Measured through the shipped schema and the live adoption set rather than read off the record. The `censo` section declares eight fields — enrolment status, the large-company flag, the public-administration budget flag, the activity start and end dates, the establishment type, the elected withholding rate, and the divergence marker. `CENSAL_ADOPTABLE_PATHS` carries three, all of them address paths: the fiscal address, the postcode, and the cadastral reference. No `censo` path is adoptable by any route. That is exactly what the decision record's consequences state, so the record and the code agree.

The three routes the decision record eliminated against a live authenticated session were not retried, on instruction and on merit. Two consultation navigations install their target and submit but return to the same page unchanged; the obligations route serves a client-rendered shell this reader cannot parse; and the activities route refuses because it identifies against the IAE matrícula, which a persona física exempt from IAE does not appear in. The third is the one that looks like a bug and is not: the refusal is present on arrival, before any interaction, which makes it evidence about the register rather than about the request, and an autónomo holding an epígrafe on their 036 is still absent from the matrícula. The route is structurally empty for individuals rather than broken for one of them.

Reopening condition, stated so this is triggered rather than remembered: direct observation of a rendered AEAT surface that carries a censal REGIME fact — enrolment state, an activity date, the establishment type, or the elected withholding rate — served as a document a reader can parse, for a taxpayer this product supports. Any one of those is sufficient and none of the three eliminated routes can supply it. A change in AEAT's rendering of the consulta page itself would also qualify, since the consulta is the surface already reachable; what it does not carry today is the regime half.

Until then the regime facts stay operator-declared through the ordinary edit path, which is a working route rather than a missing one.

## Notes

Nothing was retried and no new claim is made about AEAT. The only new evidence in this record is the schema-versus-adoption-set measurement, which is a fact about this tree; everything about AEAT's surfaces is carried from the decision record's live findings and is labelled as such.

This is closed as permanent rather than pending. A pending item implies a lead, and there is none — the difference matters because a pending item invites a later agent to spend a live session re-running the three eliminated routes, which is the specific waste the reopening condition exists to prevent. The condition is written to be met by observation arriving from elsewhere, not by effort directed at it.

The one thing that would falsify this record cheaply is the adoption set growing a `censo` path without the reopening condition being met. That is worth checking before trusting this record later, and it is a single read of the adoptable-paths constant.
