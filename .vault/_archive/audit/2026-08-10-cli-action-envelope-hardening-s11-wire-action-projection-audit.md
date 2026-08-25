---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:781412cd511cbd5b4e3ccffb6c5287f20d4355a2f3123ccb5da6c4b811352d38'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S11 wire action projection review`

## Scope

Reviewed `src/cadrumo/core/json_contract.py` and its direct round-trip tests
against the accepted ADR, S08 semantic contract, and `W02.P04.S11`. The core
module has no application import and performs projection validation only: it
does not select actions, evaluate applicability, resolve the catalogue, or
inspect the command surface. The wire vocabulary preserves S08 condition and
evidence identities, provenance, action identity, argument source/status,
conditionality, and no-recovery kinds while adding only the resolved target
command key.

Focused verification passed: eight direct tests, Ruff, and basedpyright. An
independent adversarial probe also proved action-bearing JSON round-trip,
canonical context ordering, action/no-recovery XOR, failed-condition linkage,
duplicate-evidence rejection, and immutable evidence/context mappings.

## Findings

### wire-semantic-regression-matrix | medium | Direct tests do not lock most S08 parity branches

Production currently enforces the expected strict identities, resolved/missing
binding sufficiency, evidence fact linkage and exact value type, duplicate
rejection, missing-name equality, conditionality, no-recovery restrictions,
XOR, canonical ordering, and deep freezing. The direct core tests exercise the
happy resolved projection, one terminal outcome, presentation-key rejection,
and hidden suggestion channels, but they do not regression-lock most invalid
binding/conditionality/XOR/duplicate cases or perform an action-bearing
`model_dump_json` to `model_validate_json` round-trip. Because core deliberately
cannot import the application models, these copied wire semantics could drift
without the focused suite failing.

Resolution: closed on 2026-08-10. The direct core suite now exercises
duplicate evidence and arguments, failed-condition mismatch, missing evidence
and fact references, exact value and type matching, resolved/missing binding
shape, duplicate and inconsistent missing names, action/no-recovery XOR, and
invalid conditionality. Full JSON-text envelope round trips cover both a
resolved action with target and bindings and an explicit terminal no-recovery
outcome. The tests instantiate production wire DTOs without importing or
mirroring application models.

### downstream-suggestion-cutover | low | Legacy notice producers now fail at construction until later migration waves

The intentional no-compatibility removal of `Notice.suggestion` has an exact
production break boundary of 51 `Notice(..., suggestion=...)` call sites across
27 files. The clusters are CLI diagnostics and maintenance (4 sites), ledger
CLI (15), modelo CLI/rendering (10), overview rendering (5), config CLI (11),
MCP transport (2), and application projection helpers in operator output,
overview, and wizard (4). Readers and serialized expectations also remain in
CLI, MCP schema, application/operator-surface, and tests. These are not hidden
S11 compatibility shims: strict extra-field rejection exposes them immediately.
They are campaign migration debt assigned to S12/S15 and the W03-W05 producer
waves, not evidence that core should restore free-form suggestion authority.

## Recommendations

Add a compact core-only adversarial matrix for every wire validation branch and
an action-bearing JSON round-trip. Assert literal wire enum values rather than
importing application models, preserving the core boundary.

Carry the 51-site inventory as an explicit shrinking cutover ledger. Migrate
each producer and its readers/serialized expectations to resolved typed actions
in its planned wave; do not reintroduce `suggestion`, accept reserved action
keys in context, or add a compatibility adapter. The exact break remains
construction-time Pydantic rejection at each unmigrated `Notice` producer.

The medium recommendation is satisfied. Re-review verification passed 22
focused tests, Ruff, and basedpyright with zero errors, warnings, or notes. The
low 51-site planned cutover debt remains open unchanged; no compatibility field
or action side channel was restored.
