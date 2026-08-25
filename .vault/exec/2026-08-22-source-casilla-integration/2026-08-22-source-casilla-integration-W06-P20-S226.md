---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8bcabb881b64eda60f19afbad76e9dd24661f6945526b915a856e2ac9d01f42d'
step_id: 'S226'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# Adjudicate Modelo 187's non-substitutable payer and Article 42 RGAT entity/IIC value paths, including required type-1/type-2 filer facts, before defining a canonical source, binding, casilla, provenance, collision policy, or census disposition.

## Scope

- `.vault/research/`
- `.vault/adr/`
- `src/cadrumo/_data/source_connectivity/census.toml`
- `src/cadrumo/_data/registry/aeat/modelos/187/`

## Description

- Ground official M187 filer and record populations, current bindings, mesh, census, and export surfaces.
- Record the accepted source-owner deferral decision without runtime or registry changes.

## Outcome

Payer and Article 42 entity/IIC facts remain non-substitutable. No secure source owner, resolver, binding, or export claim was added; S112 remains the separate census lane.

## Notes

- This evidence step does not classify or mutate the census.
