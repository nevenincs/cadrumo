---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6daa1d62e283ca15eebed4f09ab5216dec4dcc1ac8245579f2778f0822b01e84'
step_id: 'S85'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Establish the Modelo 390 2022 anchor census and closed projection vocabulary

## Scope

- `dev/registry/analysis/m390_2022_anchor_census.py`
- `src/cadrumo/core/_filing_projection_ref.py`
- focused core, census, and M303-to-M390 handoff tests

## Description

- Derive the exact 537 numbered-page anchors from the official parser intermediate and prove page set equality at 74, 92, 97, 19, 97, 49, 48, and 61 anchors.
- Refuse missing, duplicate, shifted, or unknown source anchors.
- Add six closed source-shaped M390 projection-reference families to the sole core filing-projection union with slot, cohort, field, and unknown-family refusal proof.
- Preserve boxes 74-83 as canonical scalar Casilla owners carried by the typed M303 fourth-quarter handoff and prove they never become projection references.

## Outcome

Commit `ea9faa0ddb` establishes the complete parser-owned census and closed projection vocabulary. Forty focused core-reference tests and six census/handoff tests pass; Ruff and formatting checks are clean.

## Notes

Canonical validation requires revision declarations, semantic-map projection entries, and generated layout fields to form an exact bijection. Those artifacts cannot land partially against the current non-projection layout, so S79 now owns declarations, application projectors, map/profile entries, and generated projection fields atomically. No semantic map, render profile, filing runtime, or registry facade changed in this Step.
