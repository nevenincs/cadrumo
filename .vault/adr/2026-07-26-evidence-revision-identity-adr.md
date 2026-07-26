---
tags:
  - '#adr'
  - '#evidence-revision-identity'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-24-evidence-revision-identity-adr]]"
  - "[[2026-07-25-evidence-revision-identity-supersede-implementation-findings-audit]]"
  - "[[2026-07-25-evidence-revision-identity-plan]]"
---

# `evidence-revision-identity` adr: `the deductible evidence gap blocks at verify, and stays out of revision identity` | (**status:** `accepted`)

## Problem Statement

Supersedes the recovery half of `2026-07-24-evidence-revision-identity-adr`. That
record was ruled `accepted` on an explicit supersede transition; implementation
proved the option unbuildable as specified, and the investigation found the
defect is not where either record placed it. The stranded-work-unit half of the
parent is already delivered and is untouched here.

One condition is classified two ways at two lifecycle points. A deductible-IVA
ledger row with no linked purchase invoice is an ADVISORY WARNING at verify,
which the outcome classifier does not block on — so verify GRANTS, freezes a
gap-carrying evidence bundle onto the revision, and locks it. The identical
condition is then a hard refusal at export and at local filing.

The consequence is a permanent dead end. The frozen bundle is what the export
gate reads, and the revision id is content-addressed over tax facts that an
evidence attach does not change, so re-calculating returns the same finalized
revision and re-verifying is idempotent. The operator is told to attach the
invoice, does so, and nothing moves.

The parent record framed this as a recovery problem and asked whether evidence
should enter revision identity. It is a prevention problem: identity was being
asked to compensate for a severity assignment that is wrong at its source.

## Considerations

- The escape hatch the promotion needed is closed on the deductible side.
  `2026-06-10-ledger-evidence-enforcement-adr` ruled this finding advisory
  CONDITIONALLY, leaving room to upgrade a category to blocking once the
  evidence-free case for that category is gone. LIVA art. 97 makes the factura
  constitutive of the right to deduct, and that article is already cited on the
  finding. The project already asserts the condition as blocking at two of the
  three lifecycle points.
- It is NOT closed on the output side, and that asymmetry is the whole reason
  this is a per-category promotion rather than a blanket one. No CLI path mints
  issued-invoice evidence, so blocking output IVA would refuse a taxpayer who has
  no way to comply. The output finding stays advisory.
- The machinery needed already exists and needs no new concept. A BLOCKING
  severity and a BLOCKING_RULE kind are declared; the outcome classifier already
  denies the grant on any blocking finding; and the bundle capture, the workflow
  gate and the pointer repair all sit under one `if granted:` branch. A
  non-granting verify therefore captures no bundle and leaves the revision
  BORRADOR by construction rather than by a new code path.
- A blocked revision is genuinely re-verifiable. The idempotent re-verify guard
  keys on a non-BORRADOR state, and verify re-reads the live transaction
  catalogue on every run, so after an attach the gap is gone, the grant is made,
  and a clean bundle is frozen. The report id folds the outcome rather than the
  clock, so the blocked and granted reports are distinct records.
- The revision id never moves, and never needed to. Attaching an invoice to an
  OUTGOING row changes no casilla, so there is no calculation difference for a
  new id to distinguish.
- Where evidence genuinely IS value-affecting it already enters identity today:
  the renta first-slice pipeline reclassifies an INCOMING row carrying purchase
  evidence as a refund, which moves the aggregation and the casilla values and
  therefore the id. Content-addressing already captures value-affecting evidence
  through the outputs it changes.
- The code already documented the promoted behaviour as fact. The diagnostic
  constant's own comment reads "Verification treats this as filing-grade
  blocking", and the module docstring says it lets the filing-grade verification
  layer decide which legally grounded side blocks. Verification did not. This is
  the sixth instance in this campaign of prose asserting a guarantee that does
  not hold — here the prose was right and the implementation was out of step.
- The verify-time advisory carried a false remedy. Its `next_action` told the
  operator to attach the invoice "then rerun verification", which could not work
  while verify granted and locked the revision. It becomes true under the
  promotion. A prior pass cleared this defect class on the export refusal, which
  is honest, and missed it one lifecycle step earlier.

## Considered options

- **Fold an evidence digest into the calculation revision id.** The parent's
  more-faithful-model option. Rejected, and the cost argument is NOT why. A prior
  pass measured the blast radius as near zero — four production deriver call
  sites and no pinned revision-id literals in tests — so the usual reason to
  prefer a cheaper fix evaporates, and it is conceded that this is the more
  faithful model of the domain. It loses on what it leaves in the store: verify
  still grants, so a revision reaches VERIFICADO_COMPLETO carrying a frozen
  bundle that asserts a deduction the taxpayer has no right to exercise, and the
  digest mints a SECOND revision beside it as the recovery. It makes the bad
  state recoverable where the promotion makes it unreachable.
- **The explicit supersede transition (the parent's accepted option).**
  Withdrawn as unbuildable. Carrying the same inputs re-derives the id it exists
  to escape, which is the no-op the amendment path already refuses; escaping that
  needs a discriminator inside identity, which is the option above.
- **Refresh the frozen bundle in place.** Still rejected. It mutates a finalized
  record, which is the immutability the bundle exists to provide.
- **Signpost only.** Still rejected as an endpoint. The signposting is honest and
  stays, but it leaves a state forming that should never form.
- **Chosen — promote the deductible finding to BLOCKING at verify, per category.**
  The condition stops being classified two ways. Verify refuses the grant,
  captures no bundle, leaves the draft open, and the operator's documented remedy
  starts working. The output-IVA side stays advisory.

## Constraints

- The promotion is per category and must stay so. Blocking the output-IVA side
  would refuse a taxpayer with no CLI path to satisfy it, which is over-blocking
  on a filing-grade surface.
- A blocked verify MUST leave the revision BORRADOR and MUST capture no evidence
  bundle. If either moved, the operator would be locked out exactly as before and
  the promotion would have changed the message rather than the outcome. This is
  the load-bearing assertion and is gated.
- The export and local-filing refusals on the same condition STAY. They become
  defence in depth over a state verify no longer lets form, and they still cover
  a revision finalized before this gate existed.
- No revision identity change, and no new persisted field. This decision
  deliberately leaves `derive_calculation_revision_id` untouched.
- Operator-facing text that becomes wrong must move in the same change. The
  export guidance said to link before `calculate`; that was true only while
  verify granted over the gap, and linking before `verify` now suffices.
- Honest limit: a revision already finalized carrying a gap is NOT recovered by
  this decision. Under `PRE_RELEASE` there is no released taxpayer data, so that
  population is local development state, and `no-legacy-compatibility` governs it.
  Prevention was chosen over building a recovery path for a state that should
  never form; that trade is accepted, not overlooked.
- The finding class beyond deductible IVA was not exhaustively enumerated. What
  would reopen the identity question is a gap class NOT detectable at verify from
  the live ledger. This one is detectable — verify already computes the exact
  predicate.

## Implementation

Landed with this record rather than handed to a plan, because the change is one
severity assignment plus the text that depended on it.

**The promotion.** In `_missing_evidence_findings`
(`application/modelo/_verification_actions.py`) the `is_deductible_gap`
discriminator already existed and both branches emitted an identical
ADVISORY/WARNING. The deductible branch now emits BLOCKING_RULE / BLOCKING; the
output branch is unchanged. Nothing else in the verify path needed touching: the
outcome classifier already denies the grant on any blocking finding, and the
bundle capture already sits under `if granted:`.

**The text that became wrong.** The export refusal's suggestion said to link
before `calculate`, which was true only while verify granted over the gap; it now
names the attach-then-verify sequence. The operator-facing locale string moved
with it across all four catalogues through the locales CLI. The verify-time
`next_action` needed no edit — it already said "then rerun verification", which
the promotion makes true.

**Gates.** The existing verify test asserted the old behaviour and was inverted
deliberately, renamed, and given the reasoning inline: it now pins that the grant
is refused, the revision stays BORRADOR, and no bundle is frozen. A new test
drives the ordering an operator actually reaches — verify, hit the refusal,
attach, verify again, granted — which was a permanent dead end before and is the
case the whole decision rests on. It also pins that the revision id does not move
across that recovery, which is the decision against identity stated as an
executable assertion rather than a claim. The output-VAT advisory test and both
export/local-filing refusal tests are unchanged and still pass, confirming the
promotion is per-category and the later gates remain as defence in depth.

## Rationale

The knockout is prevention over recovery on a filing-grade path.

The identity option and this one are not competing fixes for the same defect.
Without the promotion, verify keeps granting revisions that assert a deduction
the taxpayer cannot exercise; the identity option would make those recoverable
and leave the cause untouched. With the promotion, the identity option has
nothing left to do for this defect. That asymmetry decides it, and it survives
the cost measurement that made the identity option look cheap — the argument was
never about cost.

The conditional the governing evidence-enforcement decision left open is what
makes this a promotion rather than a reversal. It ruled the finding advisory
WHILE legitimately evidence-free cases existed, and explicitly left room to
upgrade a category once that hatch closed. On the deductible side the hatch is
closed by the statute already cited on the finding. On the output side it is
open, so that side stays advisory — which is the per-category granularity the
earlier decision anticipated, applied rather than deferred.

Content-addressing is also left doing the job it was designed for. Where evidence
is value-affecting it already moves the id through the outputs it changes; where
it is not, no new revision is needed to carry the fix. An evidence-digest term
would double-count the first case and do independent work only where, by
construction, no calculation differs.

The honest cost is stated in Constraints and not softened: a revision already
finalized carrying a gap is not recovered. Under `PRE_RELEASE` that population is
local development state, and choosing to make the state unreachable rather than
escapable is the trade taken deliberately.

## Consequences

- Good: the dead end closes at its cause. An operator who verifies before
  attaching now gets a refusal that names a remedy which works, instead of a
  grant that silently locks the target forever.
- Good: one condition, one classification. The verify, export and local-filing
  surfaces stop disagreeing about whether an unevidenced deduction is
  permissible.
- Good: no persisted-format change, no revision-identity change, no new field,
  no migration, and the frozen-bundle guarantee is strengthened rather than
  eroded — nothing existing is mutated, a bad bundle simply never forms.
- Good: the code's own documentation becomes true. The diagnostic constant
  already claimed verification treats this as filing-grade blocking.
- Accepted cost: verify refuses where it previously granted, which is a
  deliberate behaviour change on a filing-grade path. A draft that used to reach
  VERIFICADO_COMPLETO with an unevidenced deduction now stops, correctly, one
  step earlier.
- Accepted cost, and the sharpest: a revision already finalized carrying a gap is
  still unrecoverable. This decision makes that state unreachable going forward
  rather than escapable in retrospect.
- Supersedes the recovery half of `2026-07-24-evidence-revision-identity-adr`.
  Its explicit supersede transition is withdrawn as unbuildable; its
  stranded-work-unit half is already delivered and unaffected. The parent stands
  as the historical account and is not rewritten.
- Open, and deliberately not bundled: whether any evidence gap class exists that
  verify cannot detect from the live ledger. That, not cost, is what would reopen
  the identity question.
