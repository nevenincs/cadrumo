---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:dd846642da0ee0a5183f9bb2feb083ac2b64b888d042995b9dada2cf7645b000'
step_id: 'S104'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# adjudicate M193 contributor-expense semantics and source ownership from official evidence

## Scope

- `.vault/research/2026-08-25-source-casilla-integration-m193-row-source-grounding-research.md`

## Description

- Search the M193 registry, binding, source-mesh, census, row-assembly,
  persistence, revision, and export surfaces semantically and then by exact
  identifiers.
- Verify the 2024 late and 2025 AEAT record-design versions and hashes, the
  BOE form specification, and the Article-26.1.a expense-annex semantics.
- Separate the genuine direct manual `gasto.*` filing casillas from the distinct
  automated `gasto193_contributor` candidate.
- Record the current secure-owner, provenance, persistence, replay, resolver,
  and export boundary without changing a runtime or census artifact.

## Outcome

The official evidence supports a real, distinct contributor-expense type-2
record, but it does not identify a secure automated owner. The current
`gasto193_contributor` candidate is a deferred worksheet assembler whose row
identity and date are synthesised and which has no durable persistence,
calculation-revision handoff, replay, or live mesh resolver. The existing
bounded `ingress_blocked` census entry therefore remains the evidenced state:
owner `source-connectivity-campaign`, expiry 2026-12-31, and a 2026-11-30
follow-up requiring a secure persisted route and end-to-end lifecycle proof.

The direct manual `gasto.*` casillas and their fixed-record layout remain valid
filing entry and output surfaces. They do not supply source ownership. The
separate encrypted withholding repository also cannot be substituted for the
Article-26.1.a contributor-expense source.

## Notes

- No runtime, registry, source-mesh, census, or S105 change was made.
- The dormant resolver comparison of `gasto193` with registry-declared
  `gasto193_contributor` is recorded as an S105 prerequisite only; it was not
  silently repaired in this discovery.
- Independent review remains downstream of this S104 evidence record.
- Focused source-advisory and source-connectivity coverage tests passed (12
  tests); the exact M193 deferred-census ownership gate passed (1 test).
- Focused Ruff on the assembler, M193 helper, source mesh, and withholding
  repository passed.
