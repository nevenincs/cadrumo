---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3b7ca47d2293d4e24749ffde9781b6ff7b622be4879ac86cf6f29f6fa45fdc0e'
step_id: 'S205'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# amend this plan with one renderer step and one proof step per grounded row-capable format, or record no renderer when no supported format qualifies

## Scope

- `.vault/plan/2026-08-22-source-casilla-integration-plan.md`

## Description

- Translate S185's XML-positive and PDF-non-applicable ruling into format-specific implementation and proof rows.
- Add an explicit research, decision, and plan-expansion loop for the missing canonical activity-envelope source before renderer implementation.
- Require the activity-envelope implementation to reuse `TipoActividad`, join on the same durable activity identity, and prove absence, mismatch, duplication, ordering, and fabrication refusals.
- Place the XML renderer and official-XSD round-trip proof after row-casilla materialization and activity-envelope connection.

## Outcome

The plan now authorizes exactly one outbound format lane: repeated M100 XML. Steps S217-S221 own the newly exposed activity-envelope source loop and its fail-closed join; S222 renders `ActividadEstDirecta`; S224 extends the canonical parser and post-write verifier with typed row coordinates and strict equality; and S223 proves sibling alignment, deterministic ordering, maximum-six enforcement, row-coordinate round-trip, and official-XSD validity. No PDF or generic cross-format renderer was added.

## Notes

The XML schema is format-capable but the application is not yet operationally connected because required `TACT` is not inventory data. The inserted source loop keeps that missing capability in campaign scope instead of narrowing completion or manufacturing filing metadata.
