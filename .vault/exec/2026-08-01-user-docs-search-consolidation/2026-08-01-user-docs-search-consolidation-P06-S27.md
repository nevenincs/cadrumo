---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:2aa9a2d5da73169ba165ffd74244da9beedb7dee51eabc941b9678784b3b7a30'
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

### 2026-08-11 carry-forward pending gate re-run

This row stays OPEN. The decision it carries has landed; the proof cannot currently be re-taken.

Landed: the deferral is recorded in ADR Update 9, and the source retains fail-closed resolution. Registry-backed casillas remain deterministically enrolled through the validated registry projection, and a non-TOML Diseño hit resolves only when it carries a validated individual locator mapping uniquely to one revision-aware registry casilla. Modelo-only, missing, ambiguous, unreadable and unvalidated locators all remain no-target. No first-record or representative fallback is permitted.

Not re-provable at HEAD: the gate that pins the model-only Diseño hit failing closed cannot execute, because it needs the authoritative record projection that the M303 null-label gap currently blocks. The gate exists and was green when its companion row closed; it is not asserted green now, and this row is not closed on the strength of a stale run.

The substantive deferral is unchanged: an official revision-aware Diseño locator or parser schema does not exist, and the resolver must not be widened heuristically in its absence. That is a deferred contract item, not a source defect.
