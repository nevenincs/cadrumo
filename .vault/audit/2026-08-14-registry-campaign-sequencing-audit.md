---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:740a9500861f2f8457d07193319ea937e1e32219775c978d80a0ab84f96f1732'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
---

# `registry-campaign-sequencing` audit: `registry campaign sequencing`

## Scope

Five registry campaigns are in flight at once and three of them write the same
authoring trees. This document sequences them into one chain, names the single
writer of each contended tree, and records the collision that is currently
stopping all five from being verifiable. It reviews the five plans named in
`related:` against the measured state of the worktree on 2026-08-14, not against
what those plans assume about each other.

Measurement basis: a sequential run of `dev/registry/tests` at the current
worktree state (4 failed, 340 passed, 29 errors), a sequential run of the
registry domain suite, and the working-tree diff.

## Findings

### review-status-collision-corrected | critical | CORRECTS the finding below: the errors were a type mismatch, not an attestation backlog, and fixing them exposed six vacuous passes

Repair retired the finding recorded beneath this one. All 29 errors are closed
and the corrected account is more useful than the original.

The shared fixture built a filing-grade snapshot and forwarded it into a
function typed for a revision inspection, which carries neither of the two
attributes that function reads. Those tests could not have passed against any
corpus, however attested. Two sibling suites had already migrated to the
inspection-grade fixture and two were left behind; completing that migration
closed every error. The filing-grade refusal was the symptom that surfaced
first, not the cause.

Seven of the eight subjects therefore needed no attestation at all: they were
fixtures reaching for a grade their own tests never claimed. Exactly one genuine
operator gate remains, and it was not on the original list — an orden entry
carrying agent review in the impuesto-sociedades catalogue, which the generated
export-tree validation deliberately enters the filing gate against. Routing
around it was probed and honestly refused: a fabricated corpus reference is
refused, a mismatched required text is refused, and the only operator-reviewed
orden available approves a different modelo, so citing it would be a false
grounding claim.

The larger finding is what the repair exposed. Swapping the fixture alone would
have left six drift cases falsely green: each was catching the filing-grade
refusal, which is the same exception type, BEFORE reaching the defect it
injects. A guard asserting the refusal is not the review gate converted six
silent passes into visible failures. A mechanical detector for that class was
built and proven to bite. This is systemic and belongs everywhere a test asserts
on an exception type a preflight gate also raises: a passing test that never
reaches its own injected defect is worse than a red one, because it reports
coverage it does not have.

### review-status-collision | RETIRED | Superseded above; the grade mismatch was the symptom, not the cause

All 29 collection errors and 2 of the 4 failures in `dev/registry/tests` raise
from a single mechanism: `filing-grade authority requires operator_reviewed`.
The refused subjects are modelo 200 revision `2024-y-siguientes`, modelo 200
revision `2025` and modelo 390 revision `2025`, each carrying `pending_review`,
plus five DANA legal references carrying `agent_reviewed`
(`real-decreto-ley-6-2024:anexo`, `real-decreto-ley-6-2024:art-1`,
`real-decreto-ley-7-2024:art-11.2`, `real-decreto-ley-7-2024:df-14`,
`correccion-errores-rdl-6-2024`).

The fixtures die during construction, so they neither prove nor disprove the
behaviour they are named for. This is not an operator-attestation backlog: it is
test fixtures requesting a grade the corpus was never claimed to hold, after one
campaign tightened the review vocabulary and the campaigns owning those revisions
never re-attested. The class is already known and was twice repaired locally
without being recognised as systemic, most recently by the temporal-coverage row
that repaired two authority-cache fixtures dying for exactly this reason. Until
this is closed, no registry campaign can produce evidence, so it precedes all
five.

### contended-authoring-trees | critical | Three campaigns claim the modelo 303 and modelo 390 authoring trees with no declared arbiter

The export-fragment campaign generates the `modelos/303/` and `modelos/390/`
revision trees wholesale and deletes their manual predecessors. The relayout
campaign authors split revisions into those same trees. The temporal-coverage
campaign migrates python-resident regulatory data into them. Two of the three
already record the dependency in prose: temporal-coverage marks every row
touching those trees blocked on the export-fragment campaign closing, and the
export-fragment campaign carries a row whose whole purpose is reconciling the
relayout plan against generated and deletion evidence. Nothing enforces it, and
the third campaign does not record it at all.

### duplicated-ruling | high | The suite-red plan re-decides a modelo 303 split the relayout campaign already owns

The suite-red plan's row to model the 2018 mid-course AEAT split as its own
revision pair decides the same question the relayout campaign's sub-year epoch
mechanism was authorised to decide, over the same tree. The suite-red plan
states in its own description that this row is an operator ruling needing an ADR
it does not have. Executing it independently produces a second, unreconciled
answer in a tree that already has a declared owner.

### uncommitted-consolidation | medium | The in-flight modelo 303 semantic-map consolidation is coherent work and must not be discarded

The working tree replaces two per-design census modules and their two test
modules with one unified census and one unified test module, and adds a
`2024-late` mapping set. This is the shape the export-fragment campaign's
2024-late epoch row calls for, and it is the head of the chain rather than
stray damage. It is unlanded and therefore at risk from any sweep.

### narrowing-not-recorded | medium | Operator-gated rows are spread across campaigns with no single ledger

Rows that no agent may close appear in at least three campaigns: the legal
corpus vintage operator gate and its closeout, the export-fragment per-revision
operator signoff rows, and grade promotion in temporal-coverage. Each is
correctly refused in place, but there is no one list, so the chain can read
complete while several attestations sit unapplied.

### second-divergence-instance | high | The modelo-named field pattern has a second live instance on a tree this chain cannot touch

Removing the modelo-named field from the two shared catalogue and snapshot types
did not exhaust the pattern. A generic export-layout type still declares a
Modelo-303-named field, found by the structural gate written to prevent the
regression rather than by inspection. It is a genuine instance of the same
defect, and it sits on the export-layout surface the Tier 1 campaign regenerates
wholesale, so removing it from a shared type while that campaign holds the tree
would be precisely the collision this document exists to stop. It is deferred
with a stated reason in the gate's allowlist, and the gate fails if that
exemption ever outlives the defect it covers. What the standing goal still asks
for that this excludes: no generic registry type carries a modelo-named field at
all. That is untrue of the tree until Tier 1 lands its generated export trees
and the exemption is deleted.

### plan-state-drift | critical | The plans understate the tree so widely that authoring from them re-writes existing work

This is the dominant finding. Four independent confirmations, each found by
verifying before authoring rather than by reading a plan:

Two rows of the legal corpus vintage campaign were open while their code was
already implemented AND committed by an earlier session, with matching
execution records also committed. Only the checkboxes were stale.

The temporal-coverage schema-family enrolment row and the source-evidence
fingerprint row were both open while their implementations sat on disk
uncommitted, carrying 23 and 3 real tests respectively, all passing. One of the
two already had an execution record written by a prior session, itself
uncommitted.

The relayout campaign's row confining the 2024-pinned transitional rate rungs
to the 2024-covering revisions is open, while the edit is already made in the
working tree: the dated windows are removed from the two later revisions, whose
own design neutralises both slots to a zero constant. Every removed window ends
before the earliest period those revisions cover, so the change is correct.

The consequence is not bookkeeping. An agent that trusts an open checkbox and
authors will re-implement work that exists, and on a shared tree the second
implementation lands on top of the first. That is the same collision as two
campaigns writing one tree, reached from the opposite direction, and it is
cheaper to hit because nothing warns.

The chain's first job is therefore a reconciliation pass, not authoring: for
every open row across the five campaigns, establish whether its work is already
present on disk or in history before any tier writes a line. The rows found
done need records and closure, not execution.

### nota-7-uniform-gap | low | CORRECTS the finding below: there is no two-ways-for-one-shape defect, there is one uniform unimplemented note

Measurement retired the finding recorded beneath this one, which was written
from a premise that did not survive it. The correction matters more than the
original.

The driver for homing the reducido-transitorio Tipo % slot to a casilla is
Nota 8, not Nota 7: that slot's mandated constant CHANGES at the 10/4T 2024
filing-period boundary, from 00500 to 00750, and no single literal can express
a value that varies by period while a dated parameter can. The same holds for
two further slots under Nota 9 and Nota 10. So the six literal-homed slots
differ from the casilla-homed ones on the axis of whether the mandated value
varies by period, which is implemented correctly and uniformly. There is no
undeclared discriminator and no competing home for one shape.

On the Nota 7 axis all ten slots are identical and all ten are unimplemented,
the casilla-homed one included. Nota 7 is byte-identical across all six
declared designs and is PERMISSIVE — a foral-only filer *may* fill the marked
fields with zeroes. The contrast is deliberate and sits in the same note table:
Nota 5, same page and same subject, is mandatory in the indicative, and AEAT
wrote both. Nota 5 is implemented at the filing producer, matching its
carve-out list line for line; Nota 7 is implemented nowhere, and no rate, tipo,
literal or casilla path consults tax territory at all.

Because the note is permissive, writing the real rate is compliant, so the six
literals are not a mis-declaration and no filing is wrong today. What is absent
is a permitted convenience for foral-only filers. That is a low-severity gap
rather than the correctness defect first recorded, and it is uniform rather
than inconsistent.

Two constraints bind any future ruling. Note numbering is per record and per
epoch, not document-global: a second, unrelated Nota 7 governs module ordering
in another record from one epoch onward, so a ruling written document-wide
would collide with it. And two epochs have no authored map yet, so their marked
slots have no home to be consistent or inconsistent with.

### nota-7-inconsistent-homes | RETIRED | Superseded by the finding above; premise did not survive measurement

The Modelo 303 semantic maps re-home one Tipo % slot from a hard literal to a
casilla in the 2023 and 2024-early epochs, on the grounding that the bundled
design's own note table permits a foral-only filer to fill the slot with zeroes
and a hard literal cannot emit that. Six structurally identical slots carrying
the same note marker remain hard literals in all three epochs. So the same
source shape now has two homes inside one epoch with no declared discriminator,
which is the condition an exact bijection to one canonical typed authority
exists to prevent.

Two further facts make this more than an inconsistency. The re-homing amends
what two already-closed rows delivered, after their audits recorded zero
findings against the pre-amendment state, so closed work changed without a
record. And the note wording quoted so far is permissive rather than mandatory,
which is decisive: if filling the real rate is permitted, the six literals are
correct and the re-homing was unnecessary; if it is not, the six are a live
mis-declaration for foral filers, which produces valid output and raises no
refusal. That direction is the unwatched one this project has already been
burned by.

This is a tax review against official AEAT text and a semantic-home ruling
across five epochs, not a code judgement, so it is escalated rather than
decided. Measurement of every marked slot, its home per epoch, and the verbatim
note text per epoch is in progress; the ruling wants an ADR before any home
moves.

### half-built-rows | high | A row found on disk can be half-built, and the built half verifies green

The source-evidence fingerprint row asks for two things: bound the evidence
walk the way the registry tree fingerprint is bounded, and key the authority
cache on a digest of the fingerprint tuples rather than on the tuples
themselves. Only the first is built. The authority cache is still keyed on the
raw tuples, and no digest call exists anywhere in the package's uncommitted
diff. The row also asks for a before-and-after measurement against a warm real
bundled tree; no timing or count measurement exists, only an object-identity
cache-hit proof.

The built half passes its three tests, so a reconciliation pass that stops at
"tests are green" would close this row on half its contract. Finding work on
disk is therefore not sufficient to close a row: the disposition must be taken
against what the row ASKS for, clause by clause, not against whether what
exists passes.

### reconciliation-result | critical | Nine open rows are already done and nine more are half done, across all five campaigns

A read-only pass over every open row in the five plans, judging each against its
own clauses rather than against whether existing code passes, returns:

- export-fragment, 28 open: 1 done, 2 partial, 24 open, 1 operator-gated.
- relayout, 17 open: 1 done, 3 partial, 1 ambiguous, 12 open.
- suite-red, 9 open: 2 partial or ambiguous, 7 open.
- temporal-coverage, 34 open: 6 done, 2 partial, 23 open, 1 operator-gated, 2
  blocked on the tree owner.
- legal corpus vintage, 3 open: 1 done, 2 operator-gated.

So roughly a fifth of the open rows are not open. Two of the done ones are
committed under commit messages that name neither the row nor its campaign,
which is why they read as missing: one auxiliary-activity discriminator, and the
annual-summary handoff that other campaigns treat as their unblocking
precondition. A campaign cannot be sequenced off its checkboxes alone.

### audit-asserts-untrue-state | critical | A sibling audit narrates rows as closed that are open, and one of its claims is falsified by a live gate

A same-dated audit records several relayout rows as closed by other campaigns.
Its narrative does not match those rows' checkboxes, which are still open. More
seriously, its claim that a split creates no fresh Spanish label obligation is
contradicted by running the locale drift gate: the gate reports thousands of
missing keys, including the casilla labels of the very revision the claim
concerns.

An audit is the instrument later work trusts when the plan is doubted. One that
asserts a state the tree contradicts is worse than a missing audit, because it
terminates the enquiry it should start. It must be reconciled against both the
checkboxes and the live gate before either is trusted.

### cross-campaign-gate-break | high | One campaign's landed split retired a revision id another campaign's committed gate pins

Splitting the Modelo 390 annual epochs retired a revision id that a committed
disclosure-split gate hardcodes, and that gate now fails on a missing key. The
gate's own failure text anticipates this and instructs a diagnosis before
re-anchoring, which is the same instruction an open suite-red row already
carries. This is the contended-tree collision reaching a consumer rather than
the tree itself: the split was correct, the gate was correct, and nothing
connected them.

### excluded-scope-re-proposed | high | A row asks to model a split its governing ADR deliberately left refusing

The suite-red row to model the 2018 mid-course split and attribute the 2015
designs is a genuine duplicate of the relayout campaign's mechanism, and worse
than a duplicate: that campaign's completed scope rows already ruled both the
2018 split and the 2015 boundary OUT of the prescripcion-reachable window, and
recorded them as deliberately refusing rather than modelled. The row proposes to
build what an accepted decision record excluded, without citing or amending it.
It must not execute standalone. The years it names belong in the relayout
campaign's still-open row that records every deliberately-refusing year.

## Recommendations

### Tier R, before any tier below

Reconcile every open row across the five campaigns against the tree and the
history before authoring anything. Per row record one of: already done and
needing only a record and closure; partially done, with the unbuilt clauses
named; or genuinely open. Take the disposition against the row's own clauses,
because a half-built row's built half verifies green. This precedes Tier 0
because it changes what every later tier is for.

### The sequence

**Tier 0, unblocks everything.** Close the review-status collision. The subjects
are enumerated in the first finding. Decide per subject whether the fixture
should stop demanding filing grade or the campaign owning the revision should
supply attestation, and record which. No other tier can produce evidence until
this lands.

**Tier 1, the export-fragment campaign.** It is the declared single writer of
the `modelos/303/` and `modelos/390/` authoring trees. Order within it is
already fixed by the plan: the remaining modelo 303 epoch maps (2024-late, whose
work is on disk now, then 2025, then 2026), the exact-anchor census, atomic
generation with deletion of the superseded manual trees, the determinism proof,
then the modelo 390 maps and generation, then the annual-summary handoff.

**Tier 2, the relayout campaign.** Starts when Tier 1 executes its reconciliation
row, not before. Its modelo 303 rows, then modelo 390, then modelo 200, then the
consumer sweeps, locale leaves and gate re-runs.

**Tier 3, temporal-coverage.** Its rows that do not touch the contended trees are
unblocked today and should run in parallel with Tier 1: the grade and coverage
contract, the snapshot schema divergence removal, and the loader and cache rows.
Only its rows writing `modelos/303/` and `modelos/390/` wait for Tier 1.

**Tier 4, suite-red.** Retire its modelo 303 split row into Tier 2 rather than
executing it; run its remaining fixture and registry-data repairs independently.

**Tier 5, legal corpus vintage.** Its dev-screen rows are independent of every
tree above and may run at any point. Its operator gate and closeout join the
single attestation ledger recommended below.

### Enforcement

Single-writer ownership of a contended authoring tree should be declared data
rather than prose in three plans. The decision a follow-on ADR must make is
whether registry authoring-tree ownership is declared and enforced at registry
build, and what a second writer's commit does.

Open one attestation ledger listing every operator-gated row across the five
campaigns, so the chain cannot read complete while attestations sit unapplied.
