---
tags:
  - '#adr'
  - '#evidence-revision-identity'
date: '2026-07-24'
modified: '2026-07-25'
related:
  - '[[2026-07-25-evidence-revision-identity-operator-walkthrough-audit]]'
---

# `evidence-revision-identity` adr: `bundled evidence and calculation revision identity` | (**status:** `proposed`)

## Problem Statement

An operator who reaches the export evidence refusal has no way to produce a filing
that carries the invoice, for that filing target, ever again.

The refusal fires when a finalized revision's bundled ledger evidence shows a
deductible-IVA row with no linked purchase invoice. The remedy the refusal names
is to register the invoice and attach it to the ledger row. Attaching is now
possible (the finalized-modelo write guard was narrowed to exempt evidence-only
mutations), and the evidence does land on the ledger row. But the filing it was
meant to unblock never picks it up, and no sequence of shipped verbs makes it.

Three mechanisms compose into the trap. Each was measured against a real profile
on a throwaway storage root, not inferred:

- A revision bundles its ledger evidence at VERIFY, and that bundle is frozen on
  the persisted revision. The export gate reads the bundle, never the live ledger.
- `derive_calculation_revision_id` is content-addressed over the work unit, input
  values, binding overrides, casilla values and contributing transaction ids.
  Evidence references are in none of them, so re-running calculate after an attach
  re-derives the SAME revision id and returns the existing finalized revision
  untouched. Observed: identical revision id across calculate and re-calculate,
  state already `verificado_completo`.
- Verify is idempotent-guarded on its outcome, so re-verifying the unchanged
  revision returns the existing report and re-captures nothing. Observed:
  identical verification report id.

The apparent escape is worse than the trap. `work discard` marks the work unit
`descartado`; the follow-up `work create` re-derives the SAME work-unit id (it is
content-addressed over bucket, modelo, filing year, period and registry revision)
and hands the discarded unit back. Every later verb then refuses with "no active
work unit matches this modelo, year and period; run work create first", which is
the command that just failed. Observed: same work-unit id returned, state
`descartado`, calculate/verify/export all refusing. Discarding therefore strands
that (modelo, filing year, period) target permanently for that profile.

Only the ORDERING works today: linking the invoice before calculate produces a
draft whose verify-time bundle carries the evidence, and export succeeds. That
ordering is now stated in the refusal, the attach advisory and the quickstart, so
the dead end is signposted rather than silent. This record asks whether the
product should also make the recovery possible, which the signposting does not.

## Considerations

- The frozen bundle is not incidental. Bundling evidence into the revision and
  pegging it to the snapshot fingerprint is a deliberate filing-grade guarantee:
  a filed artefact must remain re-derivable from the evidence captured with it.
- Evidence is deliberately excluded from a row's tax facts. Both
  `derive_transaction_id` and the ledger filing snapshot's fingerprint field set
  omit the evidence references, which is precisely what makes an evidence-only
  attach safe under a finalized revision.
- Evidence IS value-affecting for a FUTURE calculation. In the Renta first-slice
  expense pipeline an incoming row carrying purchase evidence is reclassified as a
  refund, and a resolved invoice's taxable base and IVA override the row's own. So
  a post-attach recalculation is not cosmetic; it can legitimately change casilla
  values.
- Content-addressed reuse is documented behaviour, not an accident. The id
  deriver's own contract states that structurally identical re-runs return the
  existing revision so a second calculate is idempotent.
- The stranded work unit is a second, independent defect. Even if evidence entered
  revision identity, `work create` returning a discarded unit would still be a
  one-way trap for any operator who reaches for discard.
- Measured against the idempotency contract, the post-attach recalculate COLLAPSES:
  it returns the existing finalized revision as a matching no-op. It does not refuse,
  and it does not silently drop. `single-subject-mutation-is-idempotent-guarded`
  requires a same-key call whose CONTENT differs to refuse naming the divergent
  fields, but that clause is keyed on the record's declared identity axes, and
  evidence is deliberately excluded from all three of them — the revision id
  deriver, the transaction id deriver, and the filing-snapshot fingerprint set. So
  the system does not model the retry as content-divergent; only the operator does.
  That gap between the operator's model and the identity model is precisely what
  this record exists to settle.
- This is a stale read, not a `no-silent-under-declaration` breach, and the
  distinction is load-bearing for how urgent the fix is. Nothing is dropped: the
  attach persists the evidence reference onto the ledger row, the finalized
  revisions citing that row are returned as stale, and the CLI emits a non-blocking
  advisory naming the ordering rule and the fact that recalculating will not change
  it. The forbidden failure mode in that rule — a guarded no-op whose match omits a
  persisted field, so a retry silently loses a changed value — does not apply,
  because the changed field is not a field of the calculation revision at all. The
  frozen bundle not tracking it is the filing-grade immutability guarantee working
  as designed.

## Considered options

- **Fold an evidence digest into the calculation revision id.** A post-attach
  recalculate mints a new draft, which verifies, re-bundles and exports. Matches
  the operator's mental model exactly. Cost: changes the meaning of a documented
  content-addressing invariant and reaches the participation index, amendment and
  workflow surfaces; every revision id changes.
- **Refresh the bundle in place on the finalized revision.** Smallest change, but
  it mutates a finalized filing record, which is exactly the immutability the
  bundle exists to provide. Rejected.
- **Make the export gate read the live ledger instead of the bundle.** Removes the
  refusal but exports an artefact whose bundled evidence does not carry the
  invoice, breaking the evidence-parity guarantee the export owes. Rejected.
- **Add an explicit supersede verb that re-opens a finalized revision as a new
  draft.** Leaves content-addressing untouched and gives the operator a named,
  non-destructive path. Cost: a new lifecycle transition and its audit semantics.
- **Signpost only, no recovery (status quo after this campaign).** The refusal,
  the advisory and the quickstart now all state the ordering rule, so no operator
  is silently trapped. Cost: an operator who already hit it still cannot recover
  that filing target.

## Constraints

- Filing-grade path: any option touching revision identity or the evidence bundle
  changes persisted records that a human files outside the application, so it needs
  operator sign-off rather than an implementer's judgement.
- Revision ids appear across the participation index, amendment resolution,
  workflow runs and committed fixtures; a change to the deriver is a
  whole-repository sweep, not a local edit.
- The stranded-work-unit behaviour must be resolved either way. It is reachable
  today by any operator who follows the obvious instinct to discard and retry.

## Implementation

Not decided; this record exists to obtain the decision.

If evidence enters revision identity, the deriver gains an evidence-digest term
computed from the contributing rows' evidence references, and every consumer that
compares or stores a revision id is swept in one atomic change with its fixtures.

If a supersede verb is preferred instead, it opens a NEW draft revision from a
finalized one, carrying the same inputs and re-capturing the bundle at the next
verify, and the export refusal names that verb as the way forward.

Independently of that choice, `work create` must stop returning a `descartado`
unit as though it were usable: either it refuses with an instructive message that
names the real next step, or discard becomes reversible. Today it returns the
discarded unit and every downstream verb then denies the unit exists.

## Rationale

Deferred to the operator. The implementer's recommendation is the supersede verb
plus the discard fix: it restores a non-destructive recovery path, leaves the
documented content-addressing invariant and the frozen-bundle guarantee intact,
and confines the blast radius to one new lifecycle transition rather than every
revision id in the repository. Folding evidence into the id is more faithful to
"the revision persists its evidence, so different evidence is a different
revision", but it is the larger and riskier change and its benefit over an
explicit supersede is mostly conceptual.

## Consequences

Signposting has landed, so no operator is silently trapped and the quickstart
narrative completes end to end in the working order. What remains open is
recovery for an operator already in the trap, and the stranded work unit, which is
reachable independently of the evidence question and is the sharper of the two.

Every code claim in this record was re-verified at commit `7079c0f815` and all six
still hold; none had been closed by intervening work. The stranded work unit is
confirmed still reachable, and the asymmetry that causes it is now pinned by a test
asserting that a discarded unit resolves as absent to the natural-lookup selector
while `work create` still returns it by exact id.
