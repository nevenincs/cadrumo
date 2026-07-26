---
tags:
  - '#audit'
  - '#evidence-revision-identity'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-24-evidence-revision-identity-adr]]"
  - "[[2026-07-26-evidence-revision-identity-adr]]"
  - "[[2026-07-25-evidence-revision-identity-supersede-implementation-findings-audit]]"
---

# `evidence-revision-identity` audit: `supersede ruling review`

## Scope

An independent architecture review of the supersede-identity conflict,
dispatched while the question read BLOCKED ON OPERATOR and completed after HEAD
had moved under it. Between dispatch and review a successor decision landed:
the 2026-07-26 record supersedes the recovery half of the 2026-07-24 record,
rules the identity question NO, and its implementation - the per-category
BLOCKING promotion at verify - landed two minutes ahead of it. This review
therefore answers the four questions it was dispatched with, recomputed against
that HEAD: whether the unbuildability finding survives independent
verification, which of the two briefed mechanisms was right, whether either
fell in the class reserved for operator sign-off, and what amendment the parent
decision record needed.

Every load-bearing claim below was verified by direct read or measurement at
the current tree, not carried forward from the dispatch brief or from the prior
audits. The semantic code index was degraded throughout (last finding) and no
negative claim rests on it.

## Findings

### unbuildability-survives-independent-review | high | the mandated supersede transition cannot mint a distinct record, and the two prior investigations did not share a wrong premise

The finding is correct, verified from the schema outward rather than by
re-running either prior investigation. `derive_calculation_revision_id`
(`src/cadrumo/domain/modelos/_calculation_revision.py`) takes exactly thirteen
parameters; `ledger_filing_snapshot` and `ledger_filing_evidence` are not among
them, and the field comments on `CalculationRevision` state that exclusion as
deliberate, three times, in matching words. The model validator
`_enforce_invariants` re-derives the id from the record's own thirteen axes and
refuses the record on mismatch, so a revision's identity IS its content - there
is no field left over to make a same-input successor a different record.
Measured independently: two derivations over identical inputs return one
digest. The amendment path already meets this exact wall and says so:
`_amendment_actions.py` refuses when the minted id already exists, with the
message that no-op overrides cannot be filed as amendments. A supersede
"carrying the same inputs" is that refused no-op by construction. The parent
record's premise that the transition "touches neither the deriver nor the
frozen bundle" was wrong not in magnitude but in kind: on the identity question
the deriver and the bundle are one surface, and it is closed.

### both-briefed-mechanisms-were-correctly-abandoned | high | the lineage axis and the source-issue route each fail on grounds that verify at HEAD

The optional `supersedes_calculation_revision_id` axis is a discriminator
inside revision identity - precisely the class the parent record reserved for
the operator in its Constraints - so its withdrawal was right independent of
its technical merits. The `source_issues` route, recommended in one audit and
then withdrawn in its companion, fails on carrier semantics, and that objection
verifies directly: `CalculationSourceIssue.reason` is a closed single-value
Literal admitting only `unrouted_observation`, `binding_source` is required,
and the model docstring scopes it to a source observation that could not be
consumed by any declared binding. A deductible row with a missing invoice WAS
consumed - it contributed to the casilla value - so carrying the gap in that
envelope would assert something false about the calculation. Adopting it would
have meant widening a Literal and relaxing a required field on a strict-frozen
persisted model on the filing path: a semantic shim wearing a reuse costume,
exactly as the dispatch brief suspected. Neither mechanism should be revived.

### the-landed-resolution-survives-review | medium | the severity promotion is the right ruling and its claims hold at HEAD

The 2026-07-26 supersession relocates the defect correctly: one condition was
classified advisory at verify and blocking at export and filing, so verify
granted and froze a gap-carrying bundle that the later gates then refused
forever. Verified at HEAD: the deductible branch of the missing-evidence
findings in `_verification_actions.py` now emits BLOCKING_RULE / BLOCKING while
the output-IVA branch stays advisory; the re-verify idempotency guard keys on a
non-BORRADOR state, so a blocked revision is genuinely re-verifiable; and the
gate `test_a_blocked_verify_is_recoverable_by_attaching_and_verifying_again`
drives the full recovery ordering and pins that the revision id does not move
across it - the NO ruling stated as an executable assertion. The export and
filing refusals remain as defence in depth, pinned by the two unchanged
legacy-verified refusal tests. The supersession was the correct instrument
rather than an in-place edit: the parent was accepted and executed against, and
it stands as the historical account. No further amendment to the parent is
needed; its Implementation section is corrected by supersession, which is how
an accepted-and-executed record should be corrected.

### authority-was-exercised-defensibly-and-should-be-surfaced | medium | the NO ruling stayed outside the reserved surface, but the reservation was the operator to exercise and the closure should be ratified by them

The dispatch brief read the reserved class as binding on the surface touched,
not the magnitude of the diff, and that read is affirmed: both briefed
mechanisms touched revision identity and required sign-off. The landed
promotion touches neither reserved surface: the deriver is unchanged, no
persisted field moved, no frozen bundle is mutated, and a bad bundle now never
forms. Declining every identity option and fixing the severity instead is
therefore within implementer authority on the letter of the Constraints. The
honest residue is that the parent record framed whether recovery should be
possible as a question for the operator, and the closure answers it NO -
already-finalized gap-carrying revisions stay unrecoverable, defended as local
development state under the PRE_RELEASE regime. That defence is sound, but a
question the operator explicitly reserved was closed without them, and the
S09 row of the plan records that no operator sign-off was needed as settled.
The correct disposition is to surface the closed ruling to the operator for
ratification rather than reopen it; nothing in it forecloses the identity
option if a gap class ever surfaces that verify cannot detect from the live
ledger, and the successor record names exactly that as the reopening condition.

### plan-closed-with-exec-record-gaps | low | six checked steps lack execution records, including the one that changed source

Plan status reports exec-missing on S04, S05, S06, S08, S09 and S10. The step
rows carry honest inline dispositions (SUPERSEDED BY / RESOLVED BY with the
successor record named), which covers the spirit of closure honesty for the
no-source-change rows, but S10 landed real production and test changes and has
no execution record, and the closure rationale for the superseded rows lives in
step-row prose rather than in an exec record or close-audit note. This is a
process hygiene gap, not a correctness one.

### semantic-index-degraded-during-review | low | the code index answered confidently from 68 sections against roughly 4,546 source files while reporting itself succeeded

The mandated probes were run. The code probe for the exact concept under review
returned an unrelated packaging module, from an index carrying 68 code sections
and a generation status of succeeded - degraded while self-reporting healthy,
consistent with the two prior investigations at 902 and at 82 chunks. No claim
in this review rests on a code-index result. The vault index (16,602 documents)
was healthy and materially useful: its first result for the supersede concept
was the 2026-07-26 successor record, which is how this review discovered HEAD
had moved before ruling on a stale premise.

### stranding-check-the-escape-paths-are-open | high | a taxpayer who cannot produce the factura is not stranded, and every surface between reclassify and export was verified open

The redirect asked whether the promotion trades a recovery dead end for a
filing dead end for the lost-receipt taxpayer. It does not, on two grounds. The
legal ground: LIVA art. 97 is constitutive AND enumerative - the bundled
authoritative text (`ley-37-1992.html`, anchor `#a97`) reads "Sólo podrán
ejercitar el derecho a la deducción los empresarios o profesionales que estén
en posesión del documento justificativo de su derecho" and then closes the set:
"únicamente se considerarán documentos justificativos ... La factura original".
A taxpayer who cannot produce the factura has no right to deduct, so the
refusal refuses an assertion the law does not grant; it does not block a lawful
filing. The mechanical ground, traced surface by surface: the blocked draft
stays BORRADOR, and the finalized-modelo guard refuses ledger mutation only on
VERIFICADO_COMPLETO / PRESENTADO / PRESENTADO_SUPERSEDIDO participation -
BORRADOR participation is advisory-only (`_actions_common.py`), and update
requires only an ACTIVE row. The taxpayer forgoes the deduction honestly with
`ledger update` (clear the IVA quota and carry the gross as cost - the standard
treatment for non-deductible IVA - or reclassify the row), recalculates, and
the persist site has no single-draft constraint: a changed input set derives a
new id, mints a new BORRADOR beside the old one and repoints the work unit
(`_revision_persistence.py`). Verify reads the live catalogue, the finding no
longer fires, the grant freezes a clean bundle, and export follows. Filing
without the deduction remains available at every step; no surface refuses in
between.

### promotion-door-was-left-open-by-the-governing-adr | medium | the severity promotion exercises an explicit conditional in the accepted evidence-enforcement decision, which settles the sign-off criterion

The governing evidence-enforcement decision states verbatim that the advisory
"stays advisory while legitimately evidence-free cases exist; the section
explicitly leaves room to upgrade individual category rules to BLOCKING once
the evidence-free escape hatch for that category is closed". The promotion is
the exercise of that door on the deductible side, where the hatch is closed by
the statute already cited on the finding, while the output side stays advisory
because no CLI path mints issued-invoice evidence - the over-blocking test
applied by the implementer on the half where it bites. This answers the
sharpened sign-off question: operator-visible refusal policy at verify is
ADR-governed territory with an accepted decision already reserving the
upgrade path, not a class reserved for the operator; the reserved class in the
parent record remains revision identity and the frozen bundle, and the
promotion touches neither. An ADR was the correct instrument and one was used.
The ratification recommendation stands on process hygiene - the campaign that
benefits certified its own authority - not on any identified overreach.

### stale-draft-reverify-after-reclassification | medium | the reclassify escape has a wrong-order hazard the attach escape does not, in a pre-existing class

Verify re-reads the live catalogue for the FINDING but performs no
computed-vs-stored re-derivation of casilla values against the ledger. After a
value-affecting mutation on a draft-cited row - the reclassify escape above -
re-verifying the OLD draft therefore grants over stale casilla values that
still assert the deduction, freezing an internally inconsistent bundle. This
class is pre-existing and documented (the removal path's advisory comment in
`_actions_common.py` states that a draft citing a removed row "will assert an
income/expense no longer in the books on the next verify/file"), and it is not
introduced by the promotion. But the promotion makes the deductible gap the
most-travelled instance of it, and its remedy text "then rerun verification" is
exactly right for attach (evidence is value-neutral on an OUTGOING row) and
wrong for reclassify (value-affecting; recalculate must come first), with
nothing refusing the wrong order. A follow-on decision should weigh a
verify-time ledger-drift gate for BORRADOR drafts; the decision is named here,
not taken.

### blocking-predicate-is-laxer-than-its-statute | low | any attachment silences the art-97 gate while the statute admits only the factura original

`_row_has_linked_evidence` (`_evidence_advisory.py`) is satisfied by a
`purchase_invoice_evidence_id` OR any `attachment_ids` entry, so any linked
document silences the BLOCKING finding, while art. 97 Dos admits únicamente the
factura original (and the import/ICA documents) as justificativo. The
enforcement predicate is weaker than the statute it cites - in the taxpayer's
favour, so it is a laxity rather than a stranding, and possibly deliberate
breadth since an attachment may BE the invoice. A follow-on tightening
candidate is keying the deductible side on the purchase-invoice axis
specifically; named, not decided.

## Recommendations

Adopt no further mechanism work: the trap is dissolved at its cause, both
briefed mechanisms are correctly dead, and the parent record needs no amendment
beyond the supersession that already landed. Surface the 2026-07-26 NO ruling
to the operator for ratification, presenting it as taken-within-authority with
the reopening condition stated, rather than as a question still open. Close the
exec-record gap on the finished plan: an execution record for S10, and either
records or a close-audit note for the superseded rows, per the plan-closure
discipline. Treat the confident answers of the degraded code index as a
standing hazard until its owner rebuilds it; this review adds a fourth
measured instance.

On the redirect's questions specifically: the landed mechanism is sound and
needs no operator sign-off - the upgrade door was reserved by an accepted
decision and exercised per category, and the stranding concern is answered by
the open reclassify-and-recalculate path plus the art. 97 enumerative reading,
corroborated against the bundled authoritative text rather than a paraphrase.
Closing S03 through S09 as RESOLVED BY S10 is sound in substance because the
unbuildability argument was actually made and recorded before the withdrawal,
not asserted after it; the exec-record gap above remains the one closure
defect. Two named follow-on decisions for an owner: a verify-time ledger-drift
gate for BORRADOR drafts, and tightening the deductible evidence predicate to
the purchase-invoice axis.
