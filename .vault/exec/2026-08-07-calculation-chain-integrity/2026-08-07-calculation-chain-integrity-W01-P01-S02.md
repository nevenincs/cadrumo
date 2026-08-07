---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c446efc29f71bcf7f58040b873fba16a7e9d1c18bab33e20f690f4ada9c2e76d'
step_id: 'S02'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W01.P01.S02

## Outcome

Closed by **supersession, not by execution.** The Step's approach was implemented and then deliberately reverted before this pass began; re-executing it would undo a decision taken on the merits.

## What happened

Commit `fc0d0353b2` added the registry `output_casilla_id` selector field, its build-time validation, the projection reading it, and the TOML declaration — then reverted all four in the same change. Its stated ground:

> That change reopens the cross-domain routing-table design T-05 governs, which needs a superseding ADR rather than an implementation choice made in passing.

`W01.P01.S01`'s reading of T-05 confirms that ground independently: T-05's own closed example resolves the sibling Renta case WITHOUT moving the map into the registry, keeping the constant in its owning domain and cross-checking it against the real snapshot at build time.

## What shipped instead

The T-05 remedy proper. `RENTA_130_RETENCIONES_OUTPUT_CASILLA` lives in `domain/renta/_retenciones_routing_integrity.py` with a `CrossDomainSnapshotCheck` registered at import time and installed by name at every snapshot build. `W01.P01.S04` verifies that wiring end to end rather than trusting its docstring.

## Why the row is closed rather than left open

An open row reading "give the binding family a declared output casilla" is an instruction to a future agent to redo the reverted work. The row text now carries a SUPERSEDED marker naming the reverting commit and the ADR that owns the residual question, so the plan states the decision instead of inviting its reversal.

The residual structural question — whether a binding selector may ever declare a match casilla distinct from its output casilla — is genuinely open and is carried by `2026-08-07-calculation-chain-integrity-binding-output-casilla-declaration-adr`, recorded under `W01.P01.S45`.
