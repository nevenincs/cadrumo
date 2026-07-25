---
tags:
  - '#adr'
  - '#evidence-revision-identity'
date: '2026-07-24'
modified: '2026-07-25'
related:
  - '[[2026-07-25-evidence-revision-identity-operator-walkthrough-audit]]'
---

# `evidence-revision-identity` adr: `bundled evidence and calculation revision identity` | (**status:** `accepted`)

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

### Re-verified at HEAD `7058ef827f`

Semantic search was unavailable for this ruling — the code index was truncated
while reporting itself healthy, so a miss is not evidence. The two load-bearing
claims were re-read directly.

**The stranded work unit is live and unchanged.** `create_work_unit`
(`application/modelo/_work_lifecycle.py:57-161`) derives the id, then at `:128-130`
reads `existing = catalogue.get(work_unit_id)` and returns it if present, with no
state check of any kind. A `DESCARTADO` unit is handed back verbatim, and every
downstream verb then refuses that the unit exists. This remains reachable by the
obvious retry instinct.

**The fix is enrolment under a shape this module already has, not a new one.** The
same file already refuses a discarded unit instructively at `:239-241`, raising
`WorkUnitMutationRefusedError` with a message naming the state, and
`discard_work_unit` at `:294-296` raises `WorkUnitAlreadyDiscardedError` on a
second discard. So the refusal vocabulary, the error branch and the precedent all
exist — `create_work_unit` is the one member of the family that omits the check.
That materially lowers the cost of this half and is the reason it should not wait
on the architectural half.

**Evidence is confirmed absent from revision identity.**
`derive_calculation_revision_id` (`domain/modelos/_calculation_revision.py:288-303`)
takes work unit id, input casilla values, binding overrides, row binding values,
casilla values, relation overrides, contributing transaction ids, the two M210
axes, the borrador snapshot id and its sourced bindings, detail rows and source
issues. No evidence reference appears in the signature or the hashed payload. The
docstring states the content-addressing contract explicitly, so the reuse is
documented behaviour rather than an oversight — which is what makes changing it a
deliberate reversal of a published invariant rather than a bug fix.

`list_work_units` at `:164-183` already hides discarded units from operator-facing
discovery by default. So discovery and creation disagree about whether a discarded
unit exists: it is invisible to the list and returned by create. That asymmetry is
the defect stated precisely.

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

Ruled `accepted`, and the two questions this record bundles are ruled separately
because they have different blast radii and different urgency. The work is carried
by `2026-07-24-evidence-revision-identity-plan`.

### Ruled: the stranded work unit is fixed by refusal, and it goes first

`create_work_unit` MUST NOT return a `DESCARTADO` unit. It refuses with an
instructive message naming the real next step, in the shape the same module
already uses at `_work_lifecycle.py:239-241` — `WorkUnitMutationRefusedError`
carrying the work unit id, its state and a suggestion. Discard is **not** made
reversible: it is a durable state transition whose own docstring calls it a
tombstone rather than a delete, and making it reversible would weaken an audit
property to solve a message problem.

The refusal must resolve the operator's position rather than restate it. Today the
refusal an operator meets is "run work create first" — the command that just ran —
so the new message must name what actually moves them forward. Once the supersede
transition below exists, that is what it names; until then it must at minimum say
that the target was discarded and is not recoverable by re-creating it, which is
an honest dead end rather than a circular instruction. A gate pins that a
discarded unit refuses at create and that the refusal names its state.

This half is ordered first. It is reachable independently of the evidence
question, it converts a retry instinct into permanent loss of a filing target, and
it is enrolment under an existing pattern rather than a new lifecycle transition.

### Ruled: recovery is an explicit supersede transition, not evidence in the revision id

A new transition opens a NEW draft revision from a finalized one, carrying the
same inputs and re-capturing the evidence bundle at the next verify. The export
and internal-filing refusals name it as the way forward, replacing the advisory's
deliberate silence — which was correct only while no recovery verb existed.

Folding an evidence digest into `derive_calculation_revision_id` is **rejected**,
on three grounds and not on the ground that it is conceptually worse. It is the
more faithful model of "different evidence is a different revision"; that is
conceded. But: it reverses a documented content-addressing invariant that the
deriver's own docstring publishes as a contract; it reaches the participation
index, amendment resolution, workflow runs and committed fixtures, making every
revision id in the repository move in one atomic sweep; and this record's own
Constraints reserve any option touching revision identity or the evidence bundle
for operator sign-off rather than an implementer's judgement. The supersede verb
is ruled in **because** it is the option that does not require that sign-off — it
adds a transition and touches neither the deriver nor the frozen bundle. Ruling
the other way here would have decided, without the operator, precisely the class
of question this record reserved for them.

Refreshing the bundle in place stays rejected — it mutates a finalized filing
record, which is the immutability the bundle exists to provide. Making the export
gate read the live ledger stays rejected — it would emit an artefact whose bundled
evidence does not carry the invoice, breaking the evidence-parity guarantee the
export owes under `modelo-export-mirrors-official-structure`.

The new transition needs its own audit semantics: a bucket event recording the
supersession and the superseded revision id, and a lifecycle state that keeps the
original finalized record readable rather than rewriting it. It is a creating
mutation, so it is `idempotent_guarded` per
`single-subject-mutation-is-idempotent-guarded` — a retry resolves to the existing
successor rather than minting a second draft, and its derived id is clock-free.

### Not ruled here, and deliberately so

The sequence corpus finding from the companion audit — 106 of 281 committed
contracts executing nothing, with the local filing finish line display-only — is
the structural reason this defect shipped undetected, but it is a docs-gate
decision rather than a filing-path one. It is carried as a named step so it
acquires an owner, scoped to the 72 directly-runnable frames weighted to the
export and filing verbs, with the 96 genuinely blocked frames recording why they
cannot execute so display-only becomes a stated constraint rather than an
unexamined default.

## Rationale

Deferred to the operator. The implementer's recommendation is the supersede verb
plus the discard fix: it restores a non-destructive recovery path, leaves the
documented content-addressing invariant and the frozen-bundle guarantee intact,
and confines the blast radius to one new lifecycle transition rather than every
revision id in the repository. Folding evidence into the id is more faithful to
"the revision persists its evidence, so different evidence is a different
revision", but it is the larger and riskier change and its benefit over an
explicit supersede is mostly conceptual.

### Ruling

Ruled `accepted` at HEAD `7058ef827f`, adopting the implementer's recommendation
on both halves: the supersede transition plus the discard fix. The record above
deferred to the operator; the decision is taken here so the work becomes visible
in plan status, and it is taken in the direction that stays inside the authority
this record's Constraints allow — the supersede verb touches neither the deriver
nor the frozen bundle, so it is not the filing-grade identity change reserved for
operator sign-off. The evidence-digest option remains available and remains the
more faithful model; if it is ever wanted, it is a separate decision with an
operator in it, and nothing ruled here forecloses it.

The two halves are ordered rather than bundled. The stranded work unit is ruled
the sharper item and goes first, on the audit's own reasoning: it is reachable by
an instinct rather than by a specific sequence, it costs a filing target
permanently, and its fix is enrolment under a refusal shape the same module
already has three lines away. Holding it behind a new lifecycle transition would
keep a one-way trap open for the duration of the larger change.

One framing in this record is worth affirming rather than softening, because it
determines urgency and could easily be read as minimisation: this is a stale read,
not a `no-silent-under-declaration` breach. Nothing is dropped — the attach
persists, the stale revisions are reported as stale, and the CLI advises. The
forbidden failure mode in that rule is a guarded no-op whose match omits a
persisted field so a retry silently loses a changed value; here the changed field
is not a field of the calculation revision at all, and the bundle not tracking it
is the filing-grade immutability guarantee working as designed. That is why this
is ruled as a recovery-path gap rather than a correctness defect — and equally why
the discard trap, which does cost the operator something irrecoverable, outranks
it.

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
