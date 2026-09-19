---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:4ce5d2957a41b4d3c437c02226d35a4f275cbb38b7f63dd25d710d69799c070c'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
  - "[[2026-09-04-clitui-ledger-W01-P03-S11]]"
---

# `clitui-ledger` audit: `S11 row-level TUI hold review`

## Scope

Reviewed S11's schema-v3 union and complete matrix row holds, hold mutation
tests, gate predicates, current reference, plan, execution record, generated
index, and the five named commits. Vaultspec-RAG was attempted first; its local
code index was empty, so exact source reads, independent projection execution,
and focused/full test runs supplied the evidence.

## Findings

**Ruling: NOT ACCEPTED.** One HIGH finding remains.

The independent projection reproduces 760 observations, 769 selected edges,
693 rows, and
`sha256:6d4f8685359271136a8fdba99c84ed238bc3a3daec03b3ca55c2d671d74ab2a4`.
Exactly 680 TUI-applicable rows carry only
`g3_cli_clean_break_and_completeness`; the 13 TUI-not-applicable rows are
unheld. Union and complete matrix row validators reject missing, extra, or
alternate-gate holds, including after aggregate digest refresh. The embedded
TUI census remains one installed Overview and six component-only routes. G0
is OPEN, S11 is checked, and the named commits introduce no production TUI
implementation.

### gate-lifecycle-cannot-authorize-the-hold-lift | high | Individual G4 closes prematurely while ordered G4 can never close after a lift

`evaluate_ledger_capability_gate` evaluates G4 without any accepted-G3 state.
A matrix with a manually inactive hold and otherwise complete TUI evidence can
therefore close G4 even while the same matrix fails G0 because G0 always
requires the hold active. The committed
`test_valid_controls_close_g0_through_g3_and_lifted_hold_closes_g4` explicitly
asserts that contradictory result: G0 open and individual G4 closed.

The ordered evaluator avoids that premature closure only by re-evaluating G0.
Once the hold is legitimately lifted after G3, G0 necessarily becomes open and
the ordered evaluator marks every later gate closed=false. Thus there is no
typed state that both proves G3 was accepted and permits the ordered G4
predicate to close. The row's `tui_hold_until=G3` describes the boundary but
does not authenticate that the boundary was crossed.

## Recommendations

- Add a typed, digest-bound accepted-gate closure record or receipt to the
  campaign state. An inactive global hold must be valid only with an accepted
  G3 receipt bound to the current denominator/matrix revision.
- Require G4 to validate that G3 receipt. Make ordered evaluation preserve
  accepted prior gates while still reopening them on currentness or denominator
  drift, rather than re-failing G0 solely because the duly authorized hold was
  lifted.
- Add tests proving premature hold lift/G4 refusal before accepted G3,
  successful ordered G4 after an accepted current G3, and re-locking after
  receipt or denominator drift.

## Verification

The independent projection reproduced the exact count, hold, digest, and TUI
reachability facts above. The full matrix module passes all 222 tests. Ruff
format/check, scoped `ty`, and feature Vault checks pass. Green
hold-serialization tests do not resolve the gate-lifecycle contradiction.

## Gate-receipt remediation review

**Ruling: NOT ACCEPTED.** The ordered G0-through-G3 receipt prefix and
post-G3 hold transition close the original lifecycle contradiction, but one
HIGH attestation-binding defect remains.

Receipts are frozen, unique, ordered, ACCEPT-only, plan-owner-bound, and bind
the current denominator census, revision, and digest plus the current review
subject coordinates. Missing, forged-basis, non-ACCEPT, reordered, denominator,
census, matrix, and serialized digest drift refuse. Active pre-G3 evaluation
uses normal predicates, and the ordered evaluator preserves only the historical
G0 active-hold predicate after a current G3 receipt authorizes the lift.

### receipt-does-not-freeze-the-acceptance-attestation | high | Attestation time and receipt reviewer can be rewritten while G4 stays closed

The closure-basis digest excludes the entire `acceptance_attestation`, not only
the justified active-hold control and receipt collection. Receipt validation
copies several attestation fields but omits `attested_at` and the attestation's
matrix digest. The receipt's own `reviewer` is checked only for non-placeholder
text and is not bound to the acceptance reviewer or another reviewer authority.

Independent mutations demonstrate the gap. Advancing the acceptance
attestation's `attested_at` by one second leaves G4 closed=true. Replacing the G3
receipt reviewer with `fabricated reviewer`, then recomputing the public matrix
digest/attestation, also leaves G4 closed=true. The same attestation identity can
therefore be reminted around changed receipt state, and receipt authorship is a
mutable claim rather than a frozen reviewed fact.

Make the frozen closure basis exclude only the active hold and self-referential
receipt collection. Bind canonical acceptance-attestation content, including
its id, reviewer, ruling, plan owner, denominator, subject coordinates,
`attested_at`, and a non-circular frozen matrix/closure-basis digest. Bind the
receipt reviewer to the accepted reviewer authority or remove the independent
field. Add mutations for attestation time/digest and receipt reviewer, including
serialization round trips.

The row-level 680/13 partition and union digest remain unchanged, G0 remains
OPEN, and no production TUI changes were introduced. Ruff format/check, scoped
`ty`, and feature Vault checks pass. The full matrix module passes all 231 tests.

## Noncircular-attestation remediation review

**Ruling: NOT ACCEPTED.** The new digest domains remove the mutable receipt
reviewer and bind receipt-set identities into the attestation, but one HIGH
self-consistency fabrication path remains.

The attestation digest now covers its id, reviewer, ruling, plan owner,
pre-receipt matrix basis, denominator, subject coordinates, `attested_at`, and
receipt identity/gate-set digest. Each receipt binds that full attestation
digest and a gate-specific closure basis containing the complete attestation.
The closure basis excludes only the active hold and receipt collection; the
pre-receipt matrix basis excludes those plus the attestation itself to avoid its
direct cycle. Extra receipt fields, partial recomputations, non-ACCEPT state,
wrong order/gate, stale denominator, and stale matrix content refuse.

### self-consistent-attestation-remint-is-still-accepted | high | Recomputing the complete cycle authorizes fabricated identity and time changes

Receipt IDs accept any matching identity rather than the exact gate-derived
identity. Changing the G3 ID to `receipt.ledger.reminted`, recomputing the
attestation receipt-set digest and attestation digest, updating every receipt's
attestation and closure-basis digests, and recomputing the public matrix digest
produces a valid matrix whose G4 assessment closes. The committed ID mutation
test stops before updating those dependent receipt digests, so it proves only a
partial stale mutation.

The same full recomputation after advancing `acceptance_attestation.attested_at`
by one second also closes G4. Internal hashes prove consistency, not that the
new attestation was independently issued. No externally current authority pins
the accepted attestation content.

Require exact gate-derived receipt IDs at minimum. Bind the accepted
attestation to an external/current reviewed authority such as a separately
observed immutable acceptance-record subject and evidence coordinate, rather
than allowing the envelope to mint both the claim and every hash that validates
it. Add full-cycle mutations for receipt ID and attestation time that recompute
the receipt-set, attestation, all closure bases, receipt digests, and matrix
digest and still must refuse.

The authorized post-G3 lifecycle works for the canonical fixture, and the
680/13 row partition, union digest, G0 OPEN publication, and no-production-TUI
scope remain unchanged. Static and Vault checks pass; the full suite result is
237 passed.

## External-acceptance-anchor remediation review

**Ruling: ACCEPT.** The prior HIGH self-consistency fabrication path is closed,
and no HIGH or CRITICAL finding remains.

`LedgerAcceptanceRecordAnchorV1` is deliberately outside
`LedgerCapabilityMatrixV1` and is revalidated from serialized data at gate
evaluation. Its existing `EvidenceCoordinateV1` is required to match exactly
one independently supplied `EvidenceSubjectSnapshotV1` on subject identity,
revision, digest, observation time, and locator. The subject digest is
recomputed from the canonical external record content: acceptance-attestation
digest and identity, reviewer and attestation time, pre-receipt matrix basis,
denominator digest and revision, review-subject identity/revision/digest/time,
and the non-self-referential coordinate evidence identity, kind, role, axes,
locator, and claim. The anchor is then compared field-for-field with the current
matrix attestation. The matrix cannot embed or replace this observed authority.

Receipt identities are now exact gate-derived constants for G0 through G3,
`receipt.ledger.{gate.value}`. A changed identity therefore fails canonical
receipt validation even if the receipt-set, attestation, closure bases, receipt
attestation digests, and public matrix digest are all recomputed.

Independent full-cycle counterexamples additionally changed the attestation
reviewer, advanced `attested_at`, and changed a campaign evidence claim to
produce a different pre-receipt matrix basis. For each case I recomputed the
attestation, all four receipt bindings, the matrix digest, and a matching new
anchor; each resulting matrix passed a serialization/revalidation round trip.
Evaluation against the unchanged independently observed acceptance subject
still refused every candidate as a stale anchor coordinate. The committed
tests separately refuse absent, stale, rebound, wrong-locator, and wrong-ID
authority, while the current anchor permits the valid ordered post-G3 hold
transition. Active pre-G3 evaluation continues through the ordinary predicates,
and matrix, denominator, census, subject, or receipt drift relocks the ordered
chain.

The independent union projection remains 760 observations, 769 selected
edges, and 693 semantic rows at
`sha256:6d4f8685359271136a8fdba99c84ed238bc3a3daec03b3ca55c2d671d74ab2a4`.
Exactly 680 TUI-applicable rows carry the G3 hold and 13 non-applicable rows
carry none. The embedded TUI census remains one installed Overview plus six
component-only routes. G0 remains OPEN, S11 is checked with S12 next, and the
remediation commits contain no production TUI changes.

Verification passed: the full matrix suite (244 tests), Ruff format/check,
scoped `ty`, scoped `basedpyright`, plan check, and feature Vault checks. The
initial Vaultspec-RAG query was attempted first; the local code index remained
empty, so the ruling is grounded in whole-file reads, exact source searches,
independent projection execution, and the adversarial recomputations above.
