---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:5e1eb32d29dc385b929879cdc74c089173b1fa6f7f71f7226ce927fe71ad2fa3'
step_id: 'S27'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-04-user-docs-search-consolidation-deterministic-casilla-enrollment-research]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
---

# Design locator contract boundary

## Scope

- `dev/docs/terminology/_resolution.py`

## Description

- Ground the Diseño locator question with settled vaultspec-rag searches over the resolver, registry projection, M130/casilla-15 exact-resolution contract, and record-design coverage boundary.
- Consult the one-time SOL-high architecture authority after the source-only implementation review.
- Amend the accepted consolidation ADR in place and add the deferred plan item without changing runtime, build, or deployment scope.

## Outcome

The current fail-closed behavior is retained. Registry-backed casillas remain deterministically enrolled through the validated registry projection; a non-TOML Diseño hit may resolve only when it carries a validated individual locator mapping uniquely to one revision-aware registry casilla. Modelo-only, missing, ambiguous, unreadable, or unvalidated locators remain `NO_TARGET_ENTITY`; no first-record or representative fallback is permitted.

The decision is recorded in ADR Update 9, and P06.S27 remains open as a deferred contract item pending an official Diseño locator/parser schema. It is not a source defect or a reason to widen the current resolver heuristically.

## Notes

- No tests, builds, model downloads, live sweeps, RAG reindexing, Pagefind/runtime probes, generated artifacts, or deployment were run.
- No source file was changed in this tranche; shared peer WIP in `_resolution.py`, the ADR, and the plan was preserved and reconciled through VaultSpec's guarded document edits.
- The deferred locator work requires official source-schema evidence, revision-aware identity, provenance preservation, unique mapping, ambiguity rejection, and registry-target parity before implementation.
- Settled RAG also exposed an existing model-only Diseño success expectation in `dev/docs/terminology/tests/test_resolution.py`; it is tracked separately as P06.S28 and was neither run nor modified in this tranche.
