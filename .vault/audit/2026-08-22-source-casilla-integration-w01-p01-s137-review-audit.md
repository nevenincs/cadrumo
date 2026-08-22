---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:c3abec74db77bd88f8911c7202a5abed554d287d49af8888a1cd3ef2a9fd1d34'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
---
# `source-casilla-integration` audit: `W01 P01 S137 calculation workflow catalogue review`

## Scope

Formal review of commit `bb775a415b` for `W01.P01.S137`. The review covered
the application-owned calculation-workflow projection, its public facade, and
its unit evidence. It checked that workflow existence comes only from an
`OperatorSurfaceReconciliation`; that the closed semantic set only filters
live rows; that live command identities and canonical paths agree with the
materialised production Click tree; and that strictness, determinism,
duplicate refusal, absence semantics, and dependency direction remain intact.

Evidence included focused Ruff and compilation checks, the complete new unit
module, the production reconciliation integration gate, and a direct build of
the catalogue from the live reconciliation. The latter produced exactly
`modelo.work.calculate` at `app modelo work calculate`,
`modelo.work.wizard` at `app modelo work wizard`, and `quickfile` at
`app quickfile`. Six focused tests passed, including the independently walked
production Click reconciliation.

## Findings

No `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` findings were identified.

The builder cannot synthesize a workflow from the semantic set: it iterates
only reconciliation leaves, ignores unrelated live leaves, and refuses an
empty qualifying result. The checked-in absence test proves that omitted live
identities do not remain supported. Duplicate identity and path refusal is
covered independently, models are strict/frozen/extra-forbidding, and output
ordering is canonical by `(entrypoint_id, command_id)`. Tests construct
reconciliation inputs and assert observable projections and refusals rather
than restating an implementation constant.

The new production module imports only sibling application modules and Pydantic;
it neither imports nor dynamically resolves an entrypoint owner. Its facade
exports all three intended public symbols. The live reconciliation and direct
runtime projection also prove the canonical identities and paths rather than
relying solely on synthetic unit fixtures.

## Recommendations

Proceed with `W01.P01.S134`. Its concrete authority should obtain this
catalogue through the reconciliation-backed builder, preserving the reviewed
rule that the public semantic allowlist never becomes an independent command
existence authority.
