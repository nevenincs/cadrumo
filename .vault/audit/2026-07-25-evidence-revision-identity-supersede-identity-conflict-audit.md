---
tags:
  - '#audit'
  - '#evidence-revision-identity'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:d36faef2fa977ecc083a6e3ed7b2c41ff2cafd78ad09a66f094acc026f1f6bdf'
related:
  - "[[2026-07-24-evidence-revision-identity-adr]]"
  - "[[2026-07-25-evidence-revision-identity-plan]]"
---

# `evidence-revision-identity` audit: `the supersede transition the ADR mandates is unrepresentable under the revision-id invariant`

## Scope

Audits the buildability of the accepted decision's second half — the supersede
transition — before any of it was written. Steps S03 through S06 of the carrying
plan were dispatched for implementation under an explicit constraint: leave
`derive_calculation_revision_id` and the frozen evidence bundle untouched. The
constraint and the mandated outcome turn out to be mutually exclusive, so
implementation stopped.

A companion audit — `what the supersede design meets in the code` — reached the
same conclusion independently and landed first. It is the ruling record on this
question, and this one does not restate it or compete with it. Two investigations
converging on one unimplementability finding from different directions is worth
noting in itself; it is why the conclusion should be treated as settled rather
than as one implementer's reading.

This record carries the parts that investigation did not: the collision as a
reproduced measurement rather than an inference, the deriver's complete parameter
set and what is absent from it, and the alternative routes that were examined and
closed. Its recommendation defers to the companion audit's, which is better.

The first half of the decision — the discarded-work-unit refusal, steps S01 and
S02 — is out of scope. It landed independently and its gate is green; nothing in
this audit bears on it.

Findings were measured at commit `e4905c2791`, and every locator below was
re-read at that commit rather than carried forward from the dispatch brief.

## Findings

### the-collision-reproduces-under-measurement | critical | the successor deriving its origin's id is a measured result, not an inference from reading the deriver

The decision's Implementation section requires a transition that "opens a NEW
draft revision from a finalized one, carrying the same inputs and re-capturing
the evidence bundle at the next verify". A calculation revision's identity is
pinned to its own content: the model validator in
`src/cadrumo/domain/modelos/_calculation_revision.py` re-derives the id from the
record's fields and refuses the record when the two disagree, and the catalogue
is keyed on that same id, rejecting any key that does not equal its record's
`calculation_revision_id`. A successor carrying the same inputs therefore derives
the same id as the revision it supersedes, and cannot be persisted beside it —
not because a guard rejects it, but because it is not a distinct record.

This was measured, not inferred. Two derivations over identical work unit,
inputs, overrides, casilla values and contributing transaction ids return the
same digest, `679cee7b18420c51...`. The result reproduced unchanged across three
distinct commits over the course of the investigation, which is what makes it a
property of the tree rather than a reading of one revision of it.

### frozen-bundle-is-not-an-identity-axis | high | clearing the evidence bundle on a successor moves the id by nothing, so the re-capture clause cannot supply the distinction

The natural reading of "re-capturing the evidence bundle at the next verify" is
that the successor differs from its origin by carrying no bundle. It does not.
The deriver's complete parameter set is `binding_overrides`,
`bindings_sourced_from_borrador`, `borrador_snapshot_id`, `casilla_values`,
`detail_rows`, `input_values_by_casilla_id`, `m210_gross_income_source_mode`,
`m210_official_tipo_renta_code`, `relation_overrides`, `row_binding_values`,
`source_issues`, `source_transaction_ids` and `work_unit_id`. Neither
`ledger_filing_snapshot` nor `ledger_filing_evidence` appears in it. The one
parameter whose name suggests otherwise, `borrador_snapshot_id`, is the Modelo
100 borrador snapshot, an unrelated concept.

Their absence is deliberate and documented in the field comments on
`CalculationRevision`: both are explicitly excluded from the content-addressed id
so that capturing or re-capturing evidence does not move a revision's identity.
That exclusion is precisely the mechanism the decision's Problem Statement
identifies as the trap, and it is also what denies the successor any distinction
to be minted from. The bundle cannot both be outside identity and be the thing
that makes the successor a different record.

This is the crux of the conflict and it is not visible from the decision record,
which discusses the bundle and the deriver as two separable surfaces. On the
identity question they are one surface, and it is already frozen.

### every-escape-route-is-closed | high | the three alternatives to touching the deriver each violate a constraint the decision states explicitly

Three routes avoid extending `derive_calculation_revision_id`. Each was examined
and each is closed, and recording them is what should stop the next reader
re-deriving this.

Discarding the origin so an ordinary `calculate` re-mints it fails on the state
machine: the `DESCARTADO` branch of the revision validator requires
`discarded_at` and `discarded_by` to be set and requires `verified_at`,
`verified_by`, `filed_at`, `filed_by` and `superseded_at` to be absent. Moving a
finalized revision into that state means stripping its verification and filing
metadata — a rewrite of the finalized record, which the decision rejects by name
as the immutability the bundle exists to provide.

Minting the successor under a second work unit fails on the same class of
constraint one level up. `derive_work_unit_id` in
`src/cadrumo/domain/modelos/_work_unit.py` is content-addressed over exactly
bucket, modelo, filing year, period and registry revision, with no lineage axis
and no room for one that would not change what a work unit means. A second work
unit for one filing target would also reach every natural-lookup selector,
visible-target resolution and cross-period carry path — a materially larger blast
radius than the decision contemplates, and still a persisted-identity change.

Reading the live ledger at the finish line instead of the bundle is the third
route, and the decision already rejects it: it would emit an artefact whose
bundled evidence does not carry the invoice, breaking the evidence-parity
guarantee the export owes.

### recovery-remains-unavailable-and-the-signposting-holds | medium | no operator is newly harmed, but the gap the decision set out to close stays open

Nothing regressed. The ordering rule that does work — link invoices before
calculating — is stated in the export refusal, in the internal-filing refusal and
in the post-attach advisory, and the advisory deliberately names no recovery verb
because both candidates were measured to make the operator's position worse. That
signposting is intact and correct.

What remains open is exactly what the decision identified: an operator who has
already reached the refusal still cannot produce a filing carrying the invoice
for that target. Steps S03 through S06 stay unchecked and unstarted. The
post-attach advisory's silence about a recovery verb, which the plan expected to
replace, remains accurate rather than stale — there is still no verb to name.

### discovery-ran-without-semantic-search | low | the RAG service could not complete a search, so every claim here rests on direct reads

The `vaultspec-rag` code index was unusable throughout. Two searches were
attempted and both timed out, at 120 and then 300 seconds, against a service that
reported itself reachable while carrying an active index job; a later status read
showed the server unreachable, requests degraded, and the most recent indexing
job failed with a no-progress timeout. A miss from that service is not evidence
of absence, so no negative claim in this audit rests on one.

Discovery instead read the owning modules end to end — the revision domain model,
the work-unit lifecycle, the amendment path, the revision persistence path and
both evidence-gate call sites — and confirmed symbols by targeted grep. The
searches for a pre-existing supersede or reopen mechanism were run that way and
found none: the only supersession vocabulary in the tree is filing-driven, and
rewrites the record it marks.

## Recommendations

The decision a follow-on ADR must take is how the evidence gap enters revision
identity, given that it must. That decision is not taken here, and this record
does not carry the mechanism recommendation — the companion audit does, and its
proposal is the better one.

For the record, this investigation independently proposed a different mechanism:
an optional `supersedes_calculation_revision_id` axis contributing a payload key
only when set. It is withdrawn in favour of the companion audit's, which routes
the gap through `source_issues` — an identity axis that already exists, is
already threaded at the persist site, and whose documented purpose is precisely
that distinct resolution outcomes cannot collapse to one revision. That
alternative adds no axis, needs no new verb, and uses the content-addressing
contract as designed rather than extending it. Recording the weaker proposal and
why it lost is worth more than deleting it, because an implementer who reaches
for a new lineage axis should find that the cheaper route was already found.

What both proposals share is the authority question, and it is the operative
constraint either way. The accepted decision's Constraints reserve any option
touching revision identity or the evidence bundle for operator sign-off rather
than an implementer's judgement. Both mechanisms touch revision identity on a
filing-grade path. The reserved category is the surface, not the magnitude of the
diff — an implementer who concludes a change is safe because no existing id moves
has answered a question that was explicitly not theirs.

Whatever is decided, a hash-stability gate should land with it, pinning what the
chosen mechanism claims about existing ids. For the withdrawn proposal that claim
was that every current call site derives byte-identically; for the recommended
one it is narrower, since recording a new source issue is intended to move the id
a recalculation derives. Either way the property that makes the mechanism
defensible is the one most likely to rot silently, and asserting it in prose is
not the same as testing it.

Until that decision exists, steps S03 through S06 should stay open and unchecked
rather than being closed as deferred. The plan currently describes work that
cannot be built, and closing the steps would record it as done.

One correction the decision record should absorb: its Implementation section
mandates an outcome the schema it governs forbids. The section reads as though
the supersede verb were ruled in because it touches neither the deriver nor the
bundle. It cannot be built without touching one of them, so that reasoning needs
revisiting rather than restating.
