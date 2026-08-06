---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:0812d0d77e3596d9d591c90c8a57fc0e81aec5dad38ee7571c0678fc26ceed90'
step_id: 'S28'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Clip the Art. 81.1 month union to the Art. 58.2 anchor

## Scope

- `src/cadrumo/domain/contribuyente/family.py`
- `src/cadrumo/domain/contribuyente/tests/test_deduccion_maternidad_0611.py`

## Description

- Clip the combined Art. 81.1 month set to the Art. 58.2 entry anchor, dropping every month strictly before the entry month for a descendant carrying an entry date.
- Leave the behaviour of every non-entitling relacion unchanged, which the clip degenerates to by construction.
- Replace the union test rather than adjusting it, using the only case shape in which the two candidate rules disagree.

## Outcome

The over-grant is closed and was verified by EXECUTING the reviewer's exact cases against the shipped predicate, not by reading the change. An adoptee born 2024-01-10 and inscribed 2024-10-05 with twelve declared months now yields three months rather than twelve, recovering 900 euros. A second adoptee born 2023-03-04 and inscribed 2024-06-01 yields seven rather than twelve, recovering 500 euros.

A control case was run alongside and matters as much as the two fixes: a natural child born 2024-03-15 still yields ten months. Both this Step and its sibling narrow a window, and a narrowing that also caught natural children would have traded one over-grant for a far larger under-grant.

The defect this closes had survived review-by-reasoning. The case originally offered as the union's justification -- an infant adopted in October, where supposedly neither limb alone reaches twelve -- is false: that infant's under-three limb IS twelve, and the test nominated as proof asserted exactly that on its own first line. So the old test demonstrated that the union equalled the maximum and proved nothing about the union. The only shape in which the union genuinely exceeds the maximum is a year containing both the anchor month and the third-birthday month, and its single distinguishing month falls before the adoption. The union differed from the alternative only where it was wrong.

## Notes

The authority for the clip is the bundled AEAT manual rather than the per-article normative excerpt, which is a two-vintage hybrid tracked as its own Step. The manual states the month-of-birth rule specifically for hijos por naturaleza, while the amount generally accrues over months posteriores al momento en el que se cumplen los requisitos.

The fix landed inside a broad checkpoint commit authored by neither the implementing agent nor the coordinator. The commit subject that actually carries this change is `fix(contribuyente): clip the Art. 81.1 month window to the entry event`.

Verification was performed at the domain level with thresholds supplied directly rather than resolved, because the registry did not load in the working tree at the time -- an untracked peer construct declared a field the revision schema forbids. That made a domain-level proof the correct instrument rather than merely a convenient one.
