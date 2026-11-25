---
tags:
  - '#adr'
  - '#cold-start-performance'
date: '2026-11-05'
modified: '2026-11-05'
body_schema: 'body-v2'
body_hash: 'sha256:173b94f343e688855693e123ef7db645f4cc1ec4b0694f92ac821dbbe35fb353'
related:
  - '[[2026-11-05-cold-start-performance-registry-model-definitions-reference]]'
---

# `cold-start-performance` adr: `Shared strict-frozen configurations defer schema construction` | (**status:** `accepted`)

Accepted 2026-11-05: the operator authorized implementing the cold-start profiling findings on 2026-11-05 and approved this decision through the coordinating session the same day.

## Problem Statement

`src/cadrumo/core/models.py` declares two shared model configurations. `STRICT_FROZEN_CONFIG` already defers schema construction to first use; `STRICT_FROZEN_HIDDEN_INPUT_CONFIG` did not, so every one of its roughly 1,250 adopting models compiled a full pydantic validator the moment its module was imported, whether or not the process ever validated one. In the registry import closure alone that is `TaxpayerProfile`, `Schedule`, `ModeloIVAProfile`, `RefundAccount`, `ChargeAccount` and the two `record_row_membership` records, none of which the first registry snapshot validates.

## Considerations

- Deferral changes when a schema is built, not what it validates: strictness, frozenness, `extra="forbid"`, `validate_default` and hidden input are unchanged.
- The codebase already relies on deferral for the 354 registry-closure models on `STRICT_FROZEN_CONFIG`, and readers of `__pydantic_complete__` (`src/cadrumo/application/operations/registry_schema_validation.py:242`, `src/cadrumo/core/errors/error_codes.py:160`) already rebuild an incomplete model.
- A schema defect in a deferred model surfaces at its first validation instead of at import; that is the trade the sibling constant has already made.

## Considered options

- Defer in the shared hidden-input constant (chosen): one declaration, every adopter benefits, the two shared constants stop disagreeing.
- Per-module `defer_build` constants: rejected; it splits the shared baseline into module-local copies, which `core/models.py` exists to prevent.
- Leave eager construction: rejected; it charges every importing process for validators it may never run.

## Constraints

- Both shared strict-frozen configurations carry `defer_build=True`. Models that need a different policy keep a module-local constant, as before.
- Validation semantics, serialized shapes and published authority bytes must not change; the published component digests and snapshot-proof cells were compared and are identical.

## Implementation

We will set `defer_build=True` on `STRICT_FROZEN_HIDDEN_INPUT_CONFIG`. The module-local `_ACCUMULATOR_CONFIG` in `src/cadrumo/domain/calculations/registry/invoice_row_materialization.py` gets the same option for the same reason; it is not a shared contract.

## Rationale

Measured on the registry closure (`registry.authority`, `formula_runtime`, `schema`), import-time model completion fell from 20 models and about 27 ms to 9 models and about 5 ms across five fresh processes, with the published authority byte-identical. The change removes work rather than moving it: none of the newly deferred models is validated on the first snapshot path.

## Consequences

- Every process that imports hidden-input records stops paying for their validators until it uses them.
- A malformed annotation on a hidden-input model is reported at first use, so the owning tests that validate each model remain the guard.
- Reconsider if a host needs all schemas built ahead of a latency-sensitive phase; it can then warm them explicitly rather than at import.
