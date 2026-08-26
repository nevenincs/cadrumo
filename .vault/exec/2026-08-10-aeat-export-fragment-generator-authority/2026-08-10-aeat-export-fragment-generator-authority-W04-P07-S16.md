---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:8853efe8de4c4b4de378ab20c7bac91df86b2467699656569b91e546ed311793'
step_id: 'S16'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Prove regenerated Modelo 303 authority and the public filing-envelope boundary

## Scope

- `dev/registry/tests/`
- `src/cadrumo/application/filing/tests/`

## Description

- Reconcile the stale M303-specific request/result names to the accepted generic
  `FilingEnvelopeRenderRequest` and `FilingEnvelopeRenderResult` boundary.
- Publish `repeat = "projection_rows"` from the persisted 2023--2026 semantic
  maps into all five generated M303 targets.
- Exercise canonical generation and check mode for committed M303 authority.
- Drive a real typed M303 producer through the untouched committed 2026 layout
  to discover integration defects instead of substituting a synthetic layout.

## Outcome

Progress only; this Step remains open.

Commit `a7d532590d` republishes all five enrolled M303 trees with matching
provenance and adds the public repeat-removal refusal. The focused public proof
passes, and the M303 generated-tree selection passes 11 tests. Current HEAD also
contains the dual isolated generation/check proof and canonical fixes for the
mixed prorrata-plus-differentiated projection record and optional absent
fixed-width blank emission; their focused codec suite passes 97 tests.

## Notes

The final untouched-layout proof now reaches `m303-2026.dp30302.f022`. Official
authority defines that wire field as a four-byte IAE epigraph, while the typed
domain identity is dotted, for example `691.9`. The correct projection is
`6919`; truncation or a codec special case is forbidden. Its canonical projector
is currently being relocated from a deleted underscored module to a new public
module by another active lane, so this execution did not recreate or overwrite
that file. Reconsider closure after the relocation owner lands and the typed
wire normalization plus full untouched-layout proof and residual mutation table
pass.


## Current proof reconciliation (2026-08-26)

Commit `502796e401` repairs the M303 proof module's stale parameter bindings, binds its 2026 target to the stable official source coordinate rather than a lifecycle revision label, and aligns the cross-period refusal with `ModeloDraft`'s canonical snapshot-period coherence boundary. Before the concurrent roster transition, all 16 cases collected and 15 passed; the sole owned stale assertion is now corrected. Static compilation, Ruff check, Ruff formatting, and diff hygiene pass on the scoped file.

A current full rerun is not attributable: another active lane has renamed the generated-tree roster entry to `2026-desde-02` before the matching registry-data rename landed and has introduced a circular registry import during that transition. S16 remains open until the foreign roster/data and import transition settles and the complete proof module passes. No M184, roster, conftest, or registry-data file was changed here.
