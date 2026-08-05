---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:10ab3e7ee9a97f15c5ee2a7bb276770f3b88975dabef91727e91191a9f137980'
step_id: 'S14'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
  - '[[2026-08-04-minimo-descendientes-eligibility-deferred-descendant-axes-adr]]'
---

# Scope the Art. 58.2 missing-anchor advisory to descendants that actually carry a tranche

## Scope

- `src/cadrumo/domain/contribuyente/family.py`

## Description

- Replace the cohabitation-and-age-under-three test in
  `DescendantInfo.art_58_2_window_anchor_missing` with the full Art. 58.1 non-income
  conditions, so a descendant carrying no tranche is not reported.
- Extend the silent-where-nothing-is-lost case table with an over-25 adopted descendant.

## Outcome

The missing-anchor advisory now fires only where a missing entry date actually costs the
taxpayer something: an older cohabiting adopted or fostered child who meets the Art. 58.1
non-income conditions. A descendant already under three takes the increase through the
ordinary limb regardless, one the statute excludes from the limb has no anchor to be
missing, one not cohabiting takes no minimo at all, and one over 25 with no discapacidad
carries no tranche for the increase to attach to.

The income ceilings are deliberately not applied, and the docstring says so. They need
registry figures this layer does not resolve, and an absent rentas figure is
non-excluding anyway, so the residual over-report is a descendant whose declared rentas
breach the ceiling - a case that already carries its own advisory.

## Notes

This was found by self-review after the axis had already landed, not by a gate. The
advisory would have reported a 30-year-old adopted descendant, which is noise in the one
channel the whole Art. 58.2 disclosure depends on - and an advisory that fires where
nothing is lost trains the operator to ignore it, which is the failure mode this
campaign's own closing audit documented for a sibling collector.

Recorded as a correction rather than folded into the preceding Step: the first landing
was not a clean pass, and a record that says so is worth more than one that reads clean.
