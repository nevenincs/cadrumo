---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:8820e4545547eaf07a826c073247199a4039ced14b5b800207a0bce5b00723fe'
step_id: 'S19'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W01.P01.S19

## Outcome

Confirmed the peer-hold question before any edit, and the answer changed the Phase.

## Working-tree state

`src/cadrumo/application/aggregation/_modelo_bindings.py` carries **no uncommitted peer WIP**: `git diff --numstat` and `git diff --cached --numstat` are both empty against it.

## What the commit history shows

The site is not held because the work already landed. Two changes carry it:

- `fc0d0353b2`, "re-scope M130 retenciones output-casilla fix to T-05 pattern", implements the registry `output_casilla_id` selector field and then **reverts it in the same change**, restoring `_M130_RETENCIONES_CASILLA` and `_M130_RETENCIONES_BINDING_ID` as Python constants and `_m130_retenciones_backend_inputs` as the redirect. Its message states the ground: the schema-field approach "reopens the cross-domain routing-table design T-05 governs, which needs a superseding ADR rather than an implementation choice made in passing".
- A later change moved the constant to `domain/renta/_retenciones_routing_integrity.py` as `RENTA_130_RETENCIONES_OUTPUT_CASILLA` and registered `check_m130_retenciones_output_casilla` as a `CrossDomainSnapshotCheck`, completing T-05's actual remedy.

## Why the Step earned its keep

The Step's stated reason, that the live over-claim and the structural fix are the same code site, held. The collision it caught was with *landed* work rather than in-flight work, which the working-tree check alone would have missed entirely.

Editing `_modelo_bindings.py` per `S02` and `S03` as written would have re-reverted a decision taken deliberately forty minutes earlier, and reopened the design question the ADR now carries.
