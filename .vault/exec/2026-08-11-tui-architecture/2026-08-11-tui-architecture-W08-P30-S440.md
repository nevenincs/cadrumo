---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:0cd29627e9284f7357151e77bb84e90feb54799603d7b733f3ce1bdc79e07a79'
step_id: 'S440'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Write record-qualified casilla labels to the key the resolver actually reads. A record-qualified casilla does not localize under its raw identifier: the registry gives it an encoded key, so DP200018:00588 resolves through casilla.x-8h834c1g60ojgehg60qjge0. Labels written under the raw id are accepted by the catalogue and never read, which made 44 of them dead weight and made an earlier progress count measure the catalogue rather than the resolver. Fill the canonical keys from those labels, delete the dead ones, and settle the last four casillas against their authority's own preimage.

## Scope

- `src/cadrumo/locales/*/modelo/schema/200.yml`
- `dev/locales/tests/test_casilla_label_matches_pinned_official_text.py`

## Changes

Unlabelled M200/2024 casillas: 4 -> 0. The runtime localization gate passes for
the first time in this campaign, down from 644 failures.

A DEFECT IN MY OWN EARLIER WORK CAME OUT OF FIXING THE LAST FOUR. A
record-qualified casilla does not localize under its raw identifier. The
registry gives it an encoded key, so DP200018:00588 resolves through
`casilla.x-8h834c1g60ojgehg60qjge0`. Every composite label written in S431, S432
and S438 went to the RAW id: the catalogue accepts that key and the resolver
never reads it, so 44 labels were dead weight.

The failure was invisible because the encoded keys already carried labels, so
the resolver was satisfied and my raw-key writes changed nothing. It also means
S432's claim that 38 casillas became labelled was measured against my own
catalogue accounting rather than the resolver's, and that count was wrong. The
resolver's own numbers are the ones this Step reports.

70 canonical keys were filled from those derived labels and all 176 dead keys
removed through the owning CLI.

THE LAST FOUR SETTLED ON THEIR AUTHORITY'S PREIMAGE. Their pins appeared to
match nothing because the blocker cohort stores the design text WITH the
embedded line wrap, while a shipped label collapses it -- so hashing the shipped
form never matched. Comparing through the preimage where an authority still
holds one, whitespace-normalised on both sides, resolves it: a line wrap is not
different text, and every difference that is a difference still shows. That is
why the normalisation is whitespace-only.

01264, 01265 and 01266 are confirmed as the Club Natacio Barcelona
reconstruction rows by their own pins.

## Notes

A REGISTRY DEFECT IS CONFIRMED AND DELIBERATELY NOT FIXED. Those three
casillas declare section '2025_innovacion_tecnologica_it' and
semantic_role 'is_deduccion_idi_innovacion_tecnologica', and their pinned
official text is the Club Natacio Barcelona reconstruction. The section and role
are wrong. The label is now correct regardless, because it comes from the pin.

semantic_role drives calculation dispatch, so changing it is a filing-behaviour
change, and nothing in the design or manual says which role these rows should
carry instead. Guessing would move a deduction between calculation families to
tidy a label. It is left for an explicit registry decision.

TOOLING GAP, worth its own fix: dev.locales has set-batch for writes but only a
single-key remove, so deleting 176 keys meant 176 interpreter starts at about
ten seconds each. The operator stopped it as a suspected hang; it was not, but
half an hour of process startup to delete 176 map entries is a real defect in
the tool rather than a cost this work should absorb.
