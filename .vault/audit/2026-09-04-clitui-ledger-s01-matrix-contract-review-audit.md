---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:f978c4c7842abf7976ad43940a7975780653842bc5297df0872a981eb53bdcb1'
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

### denominator-completeness-retest | critical | OPEN: persisted claims still substitute for a live complete census

Corrective source commit `2bf572bcb89b2aaaa46ccd5c04cdc8d6028c98ca`
adds accepted/current denominator snapshots, source categories, canonical entry
digests, subject snapshots, and drift comparison. Those types improve the
representation but do not close the original gate bypass. A self-consistent
one-row census containing only `BACKEND_ONLY` still closes G0; no validator
requires observation of every mandatory denominator source stream or connects
the snapshot to a live census authority. More importantly,
`evaluate_ledger_capability_gate` makes both live observations optional and
replaces absence with `matrix.current_denominator` and
`matrix.current_subjects`. An explicitly supplied empty subject observation is
also replaced because the fallback uses truthiness. The retest therefore closed
G0 for all three cases: one-row/single-source census, omitted observations, and
explicitly empty observed subjects. Denominator comparison also ignores
`revision` and `observed_at` when entries are unchanged. G0 remains capable of
attesting its own freshness instead of failing closed on unavailable, partial,
or stale live observation.

### mandatory-row-closure-retest | high | OPEN: CLI-owned authority may remain unclassified at G0

Per-axis applicability rationale and review evidence are now mandatory, an
all-`NOT_APPLICABLE` row is rejected, and every incomplete implementation/proof
assessment requires an affected-axis finding. These parts of the original
finding are resolved. The unresolved-work rule does not include ownership
state, however: an initially `CLI_OWNED`, migration-incomplete row whose axes
are otherwise `PROVEN` needs no `AUTHORITY` finding or next closure action and
can close G0. That leaves identified CLI policy without the mandatory classified
closure work the matrix is intended to drive.

### evidence-coordinate-integrity-retest | low | Informational: shape is resolved; currentness remains tracked by the critical finding

Role-to-kind-to-axis contracts, single-axis baseline/review coordinates, global
evidence-ID uniqueness, and explicit subject revision/digest/time matching now
reject the original wrong-role, wrong-axis, and duplicate-ID probes. Supplying a
different observed digest correctly opens G0. The freshness conclusion remains
part of `denominator-completeness-retest`, because omitted or empty observations
silently select the persisted subjects and close G0; the new metadata is not a
live check unless a caller voluntarily supplies a non-empty external tuple.

### authority-proof-history-retest | high | OPEN: initial ownership is not monotonic across matrix revisions

Within one row, annotations, delegation, and migration-completed state are now
consistent, and a row declared initially CLI-owned retains direct-backend and
adapter-detector requirements after cutover. The matrix has no accepted prior
ownership snapshot or comparison, though. A later generated row can change
`initial_cli_ownership` from `CLI_OWNED` to `NOT_CLI_OWNED`; G1 then closes
without migration completion, direct backend evidence, or an adapter detector.
`frozen=True` prevents mutating one Python instance but does not make the fact
monotonic across persisted matrix revisions.

### g0-review-attestation-retest | high | OPEN: review presence is not bound to the reviewed matrix revision

G0 now requires the exact `INDEPENDENT_ENGINEERING_REVIEW` role and rejects its
absence. The coordinate does not carry a ruling or the reviewed denominator and
matrix digest, so any current review-kind subject with all axes and an unrelated
bounded claim satisfies the predicate. The same review coordinate can be reused
after rows, semantic homes, applicability, findings, or denominator acceptance
change. The scalar plan-owner field likewise accepts `arbitrary-other-plan`; it
is not constrained to the accepted `clitui-ledger` owner or bound to plan
evidence. Review and sole-owner presence therefore do not prove acceptance of
the exact frozen campaign state.

### resolved-gate-retests | low | Informational: the remaining original predicate exploits are closed

Adversarial retest confirms the corrected source rejects an unresolved
proof/implementation axis without a finding, an all-non-applicable row,
`CLI_REFUSAL` evidence on the backend axis, and globally duplicated evidence
identities. Explicit subject-digest drift opens G0. G2 opens for a backend with
`surface_state=PARTIAL` even when direct test evidence is present, missing
independent-review evidence opens G0, and G4 now scans and blocks a finding on a
row whose TUI axis is non-applicable. Import, byte-compilation, Ruff, and diff
whitespace checks pass. This subsection records resolutions and is not an open
LOW finding.

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
9. Following corrective retest, make observed denominator and subject inputs
   mandatory for G0 and reject empty, duplicate, unavailable, partial, or
   revision-stale observations. The live census producer must prove every
   mandatory source stream, including an explicit reviewed zero when a stream
   has no entries; self-consistent caller-authored snapshots are not live proof.
10. Bind the accepted row census to immutable initial-ownership dispositions and
    compare them on every regeneration. Require a current `AUTHORITY` finding
    for every incomplete CLI-owned migration.
11. Bind independent review to an explicit `ACCEPT` ruling and the exact matrix,
    denominator, and plan-owner digests. Reject a review for any earlier matrix
    revision and constrain the singular owner to the accepted `clitui-ledger`
    plan identity.
12. Re-review disposition: **NOT ACCEPTED**. Open severity is one CRITICAL
    currentness/denominator defect and three HIGH authority/classification/
    attestation defects. The informational LOW retest entry records corrected
    behavior and is not an open finding.
