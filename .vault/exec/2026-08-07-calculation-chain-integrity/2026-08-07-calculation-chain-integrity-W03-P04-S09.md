---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4199d1ba6a6355ce0a47e36af9d790a79ecc976cea5ec8e43e81fa4a50281639'
step_id: 'S09'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec `W03-P04-S09`: Reconcile the candidate placements for the activity-type axis

## Scope

- `.vault/adr/2026-08-07-calculation-chain-integrity-activity-type-placement-adr.md`

## Summary

Reconciliation only; no code changed, per the step's no-implement constraint.

Semantic search first, then each candidate was read for what it HOLDS rather
than what it is named. That surfaced a fifth placement the step did not list and
changed the ruling: a proposed per-activity profile row model already adds *Tipo
de actividad* as part of the AEAT-recorded triple, which is the value-side home
the evidence supports.

Two measurements decided the rest. The M100 2025 revision carries the
`reg_estima_directa` and `reg_estima_obj_agricola` partitions concurrently, so a
per-taxpayer scalar cannot represent a filer holding both — the refutation is
structural, not a matter of degree. And casilla `0166`, despite the name
`irpf_ed_actividad_tipo_clave`, is `data_type = "text"` scoped to the directa
section, so it is an epígrafe key inside one partition rather than a
discriminator across partitions.

The ruling is that the axis is a JOIN, not a new field: the activity-type value
is owned by the profile activity row, and the transaction carries a reference to
the slot rather than a copy of its type. Both blocked consumers — the retención
rate narrowing and Modelo 130 casilla 08 — need the same mechanism, which is
what makes one placement sufficient.

Two costs are recorded rather than absorbed: the value-side home sits in a
`proposed` ADR, so the build acquires a sequencing dependency; and whether AEAT's
*Tipo de actividad* code set discriminates at the granularity RIRPF art. 95
needs, including the 1 % engorde carve-out, is an open grounding gap that must
close before the rate mapping is written.
