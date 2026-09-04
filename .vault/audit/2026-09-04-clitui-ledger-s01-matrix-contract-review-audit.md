---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:5979889660834e18a295fc8b0186fa5bd8f1b2ae3edc6e876e0824f1d448dd50'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-adr]]"
---

# `clitui-ledger` audit: `S01 matrix contract implementation review`

## Scope

Mandatory formal review of approved plan step `W01.P01.S01` at commit
`676fd04f59`. The review compared `clitui_ledger_capability_matrix.py` with the
accepted `clitui-ledger` ADR, research and reference census, the exact G0--G4
plan predicates, and the nearest live-tree and freshness gate analogues. It
covered stable identity, every mandatory row field, applicability and
`NOT_APPLICABLE` handling, evidence role/axis integrity, duplicate identity,
freshness, gate ordering, and newly discovered-capability reopening.

The module imports, byte-compiles, and passes Ruff. Adversarial construction was
then used to exercise semantic detector teeth. Those checks demonstrate that
several structurally valid matrices close gates without satisfying the decision;
therefore S01 is not accepted in its reviewed revision.

## Findings

### denominator-completeness | critical | G0 can close over an incomplete or content-free denominator

`evaluate_ledger_capability_gate` treats any non-empty `rows` tuple as a frozen
union denominator. A one-row matrix closes G0 even when every axis is
`NOT_APPLICABLE`; the contract has no live-census identity set, census digest,
expected-versus-observed comparison, or generation snapshot to establish that
CLI endpoints, backend-only operations, missing products, registry routes,
artifacts, and supported surfaces were all enumerated. The standalone
`reopened_gates_for_new_capability` function reports which gates should reopen
only after a caller already supplies a discovered row; it neither detects a new
live capability nor binds prior closure to the denominator snapshot. This makes
the G0 denominator-and-ownership freeze predicate bypassable and leaves later
waves able to rely on a false foundation.

### mandatory-row-closure | high | Unresolved and non-applicable obligations need no reviewed finding

An applicable axis may be `UNPROVEN` without evidence and without any
`CapabilityFindingV1`, while an all-`NOT_APPLICABLE` row needs only the row-wide
`applicability_reviewed=True` assertion. Both close G0. The single Boolean does
not carry an independently reviewable decision or rationale for each axis, and
the model forbids evidence on non-applicable assessments, so an erroneous
blanket exemption has no bounded review coordinate. Partial, absent, or
unproven obligations likewise need no blocker and next closure action. This
contradicts the matrix requirement that every row carry explicit axis
applicability and that unresolved work be classified with its next action.

### g0-baseline-role | high | Any evidence role is accepted as G0 baseline proof

G0 checks only whether an applicable assessment's `evidence` tuple is non-empty.
A backend assessment marked `PROVEN` closes with a `CLI_REFUSAL` coordinate and
no `BASELINE` coordinate. Because role-to-axis constraints are not enforced,
structural evidence presence substitutes for the specific baseline claim the
gate names.

### backend-product-predicate | high | G2 closes for a partial backend without direct behavior proof

G2's `_assessment_is_proven` examines only `AxisAssessmentV1.proof`. A backend
assessment with `surface_state=PARTIAL`, `proof=PROVEN`, and a generic `BASELINE`
code coordinate closes the backend obligation. No `DIRECT_BACKEND_BEHAVIOR`
coordinate is required. This violates the accepted G2 predicate that the
backend product itself is complete and directly proven; it also lets proof
metadata stand in for implementation state.

### evidence-coordinate-integrity | high | Evidence roles, axes, uniqueness, and freshness are not authoritative

Evidence-role validation covers only six test-only roles and does not define the
axes each role may prove. G3 accepts `CLI_ARTIFACT` evidence stored solely on the
backend assessment, and G4 accepts campaign `TUI_PARITY` and `TUI_REACHABILITY`
coordinates whose `axes` contain only `BACKEND`. `MATRIX_PUBLICATION` and
`INDEPENDENT_ENGINEERING_REVIEW` also have no kind/axis contract. Evidence IDs
are unique only inside one assessment or the campaign tuple, so the same stable
ID can be reused with conflicting claims across axes and rows. Finally, a
coordinate contains no source revision, content digest, observed-at generation,
or validation result; an arbitrary non-placeholder locator remains accepted
after its subject changes or disappears. These holes allow unrelated,
duplicated, or stale evidence to close gates.

### authority-proof-history | high | G1 proof obligations disappear when a mutable flag is cleared

Direct backend behavior and adapter-detector evidence are required only while
`authority_migration_required` is true. The contract does not derive or retain
that fact from an immutable initial ownership disposition, and it does not bind
`CLI_OWNED`, `DELEGATING`, or `cli_delegates_to_canonical` to consistent state
transitions. A migrated row can therefore clear the flag and annotation and
close G1 without either required test. A row may also claim `CLI_OWNED` while
`cli_delegates_to_canonical=True`, or claim `DELEGATING` while that Boolean is
false. The authority-recovery gate needs monotonic migration history rather than
a self-declared current switch.

### g0-independent-review | high | G0 does not require its planned independent acceptance evidence

The plan closes G0 only after independent engineering review accepts the frozen
matrix, and the schema defines `INDEPENDENT_ENGINEERING_REVIEW`, but the G0
predicate never requests that campaign evidence role. A matrix can therefore
declare G0 closed before the required S14 adjudication exists.

### g4-gap-scope | medium | G4 ignores blocking findings on TUI-non-applicable rows

G4 inspects findings only while iterating rows whose TUI axis is applicable.
The accepted predicate instead says no blocking gap may remain on any applicable
axis. A row with TUI `NOT_APPLICABLE` and a finding affecting another applicable
axis is invisible to this exact predicate. Ordered evaluation may catch some
gap classes in earlier gates, but that is not equivalent to G4's complete
blocking-gap rule and leaves classes scoped differently by G1--G3 unguarded.

## Recommendations

1. For `denominator-completeness`, add a typed denominator census contract that
   binds the matrix to the complete observed identity set and a stable source
   snapshot. Make missing, extra, unreadable, ambiguous, and post-generation
   drift states explicit G0 blockers. Reopening must be computed by comparing
   the current live census with the last accepted closure snapshot.
2. For `mandatory-row-closure`, require an axis-scoped reviewed applicability
   disposition and bounded rationale. Require every `ABSENT`, `PARTIAL`, or
   `UNPROVEN` applicable obligation to carry at least one affected-axis finding
   with gap class and next closure action; reject rows with no applicable
   obligation.
3. For `g0-baseline-role` and `evidence-coordinate-integrity`, define and enforce
   a role-to-kind-to-axis table, global evidence identity uniqueness, and a
   revision/digest freshness coordinate validated against the current subject.
   Gate predicates must request the exact evidence role on the exact axis they
   claim to close.
4. For `backend-product-predicate`, require backend `surface_state=PROVEN`,
   backend proof `PROVEN`, and direct real-behavior evidence at G2. Keep the
   composition, artifact, provenance, registry, and proof axes independent.
5. For `authority-proof-history`, model initial CLI ownership and completed
   migration as monotonic reviewed facts. Validate annotation/Boolean
   equivalence and require migrated rows to retain direct-backend and detector
   coordinates after cutover.
6. For `g0-independent-review`, require current
   `INDEPENDENT_ENGINEERING_REVIEW` campaign evidence before G0 closes.
7. For `g4-gap-scope`, scan every finding on every row and block when any
   affected axis is applicable, independent of TUI applicability.
8. Add adversarial S02 tests for each false closure above, including a one-row
   denominator, all-axis non-applicability, missing findings, wrong-role and
   wrong-axis evidence, cross-row duplicate IDs, stale subjects, partial backend
   state, erased migration history, absent engineering review, and non-TUI-row
   G4 findings. S01 can be accepted only after the critical and high findings
   are corrected and those detector tests fail on representative defects.
