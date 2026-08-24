---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0be2ff48a4d6dad191e2e1689ea5b4ba40dbb728417a1b0eb7681c7b4f354396'
step_id: 'S225'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# Adjudicate Modelo 036's exact event-driven profile source as manual-by-design and retain the human-filed no-local-submission boundary

## Scope

- `src/cadrumo/application/registry/source_connectivity.py`
- `src/cadrumo/_data/source_connectivity/census.toml`
- `dev/source_connectivity/`
- `.vault/reference/`

## Description

- Reuse the canonical `RegistryDestinationCandidate`, census, source ownership, and projection authority after semantic discovery and whole-file reads.
- Extend the existing coordinate union with the pre-existing closed `CensoModeloEventKind`; retain its exact selector through the existing registry selection call.
- Record the Modelo 036 profile binding and event casilla as a manual-by-design source disposition with official, registry, resolver, and lifecycle grounding.
- Repair discovery-only AST handling of declared `_leaf` handler defaults and local aliases so exact-one census discovery can inspect the current command specifications without executing them.
- Prove exact event selection, refusal of `AD-HOC` substitution, profile ownership uniqueness, remainder-drift mutation, and both explicit and fallback command handlers.

## Outcome

The source-casilla campaign now owns the Modelo 036 source adjudication directly. The accepted row scopes `source_ownership:profile` to the exact Modelo 036 binding and semantic casilla and records why the operator remains authoritative. No source resolver, CLI handler, persistence path, producer, export layout, or local filing action was added.

Focused Ruff, three isolated M036 source-census tests, seven discovery tests, and two isolated M036 registry binding/foundation tests passed. The full all-capability census remains visibly blocked by unrelated calculation-helper digest drift, so this step records only the completed M036 source boundary and does not assert campaign-wide closure.

## Notes

The roll-up S73 record retains the global prerequisites before a real composed closure row may be claimed: repair the remaining-calculation-helpers digest drift and restore full registry validity for Modelo 303 revision `2023` and Modelo 322 revision `2008-2022` deadline-window authority. S72 and S11 remain open.
