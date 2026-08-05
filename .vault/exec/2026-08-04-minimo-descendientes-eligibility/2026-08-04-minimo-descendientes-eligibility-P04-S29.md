---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:e69a9a16279ee569494c754a6c997652fa680c6259c5435d3f4a83996150fa31'
step_id: 'S29'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Declare the Art. 81.1 population as its own closed set and gate the month resolver on it

## Scope

- `src/cadrumo/core/_descendant_relacion.py`
- `src/cadrumo/domain/contribuyente/family.py`

## Description

- Declare the Art. 81.1 maternidad population as a closed set in the core layer, beside the Art. 58.2 entitling set and deliberately separate from it.
- Gate the contributing-months resolver on that set instead of on the ordinary-eligibility predicate alone.

## Outcome

A descendant born 2023-05-01 under a temporal acogimiento, cohabiting, with twelve declared months, now yields zero contributing months where it previously yielded twelve. That recovers 1.200 euros of under-declared tax per affected child-year, verified by execution against the shipped predicate.

The separation of the two sets is the fix rather than an incidental tidiness. The month resolver had gated only on the ordinary-eligibility predicate, which is the Art. 58.1 test and deliberately assimilates temporal acogimiento so that carer takes the minimo tranches. Art. 81.1's population is strictly narrower, and conflating the two is precisely what produced the over-grant. Keeping the sets apart in one declared home makes the narrowing auditable rather than implicit.

## Notes

The authority is byte-stable across the served window: the deduction no resulta aplicable in the case of nietos and other descendants by consanguinity other than children, nor for acogimientos familiares simples, de urgencia o temporales, nor for minors held under judicial guarda y custodia.

The case was fully representable and reachable through the documented entry flag before this change, because the temporal member exists on the relacion axis precisely to let that carer record a truthful value. The exclusion test shipped with the original window asserted only that the ENTRY WINDOW is zero for an eight-year-old temporal placement; it never put an under-three temporal placement through the month resolver. That is the landing-one-half-of-a-pair shape, which this Phase produced three separate times.

Deliberately NOT built: a member for grandchildren. A cohabiting grandchild under three is Art. 58.1-eligible and Art. 81.1-excluded, so it currently records as an ordinary descendant and takes twelve months. That is a representability question about the axis of ADR shape, not a patch, and folding it in here would have decided it silently.
