---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:067538a11119b61cb01aa224989719e06a5d66a855fd4c024d8e669ccdfcf059'
related: []
---
# `object-name-declustering` audit: `S27 implementation review`

## Scope

The unrelated AST declaration and eviction-root test hunk in the same dirty test file was excluded from S27 findings.

The review checked that rehearsal requires the verified copy's canonical inventory
digest to equal the supplied current inventory digest, records the verified copy's
digest in the receipt, and binds the authored manifest inventory only as part of the
exact canonical manifest digest. It also checked the positive control and anti-vacuity
floor: both tests create a real Python declaration, assert that its census digest moves,
and respectively prove fail-closed stale-supplied evidence and successful current-evidence
receipt generation. No safety or intent defect was found in the runtime contract.

## Findings

### incomplete-type-suppression | medium | The positive-control test introduces a type-gate failure

Both arguments in the multiline `build_manifest_components` call are incompatible with
the mutable graph protocols under ty's structural check. A single narrow
`ty: ignore[invalid-argument-type]` suppresses only the diagnostic on its own line:
placing it on the `inventory` keyword leaves the positional `manifest` diagnostic, while
moving it to `manifest` leaves the `inventory` diagnostic. In both live arrangements,
`uv run ty check` reports `invalid-argument-type` in the new S27 test and exits 1.
The same invocation also reports one pre-existing production diagnostic and two
diagnostics in the excluded peer-owned AST hunk; those are not S27 findings. The focused
runtime behavior is otherwise green: both S27 tests pass, and the complete rehearsal
module passes 41 tests. Ruff lint and Ruff format checks pass for both changed files.

## Recommendations

Apply the narrow `invalid-argument-type` suppression to both incompatible argument lines,
or use an equivalent call-level form that suppresses both diagnostics without hiding
other error classes. Then rerun the two S27 tests, the full rehearsal test module, Ruff
lint, Ruff format, and the focused ty check. Keep the receipt assertions and both
digest-movement anti-vacuity assertions unchanged.

## Remediation re-review

Resolved: `incomplete-type-suppression` is closed. The live multiline call now applies
the narrow `invalid-argument-type` suppression to both protocol-incompatible arguments.
The focused ty check no longer diagnoses the S27 call. It still exits 1 for three
out-of-scope diagnostics: the pre-existing `frozenset[Unknown]` return in rehearsal and
two unresolved AST attributes in the excluded peer-owned test hunk.

Both S27 behavioral tests pass after remediation. Ruff lint and Ruff format checks pass
for both changed files. The earlier complete rehearsal-module run passed 41 tests. Final
S27 status is no open finding at any severity.
