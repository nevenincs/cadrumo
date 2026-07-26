---
tags:
  - '#audit'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
  - "[[2026-07-25-censal-profile-autofill-adr]]"
  - "[[2026-07-25-censal-profile-autofill-tooling-honesty-audit]]"
---

# `censal-profile-autofill` audit: `campaign close honesty review`

## Scope

The campaign-close honesty review of this feature, required before the campaign is
declared structurally complete. It was commissioned as a persona switch: inherit the
campaign cold, and treat the closed task list and the reviewer's own earlier summaries
as claims to check rather than as context to build on. That framing is the reason two
of the entries below are the reviewer's own prior claims failing the check, and it is
worth preserving because the alternative framing - review the campaign you remember -
cannot produce those two entries at all.

The review read the twenty-three Steps of the plan, their twenty-three execution
records, and the code each names, against commit `01decbae15`. It was persisted at
`cbbe671fbf`, and the interval is not cosmetic: one finding closed inside it. Every
entry below therefore states the commit its claim is measured at, and where a finding
has since been closed the closing commit is named. A record that leaves a fixed finding
stated as open misdirects a later reader exactly as a stale report misdirects a
coordinator, and this campaign has already paid for that mistake twice.

The commissioning brief asked for breadth over polish - twenty honest findings ahead of
five finished ones - and explicitly forbade fixing anything. Nothing here was fixed by
this review. Two items were filed as tracked work, one has since been closed by its
owner, and one is being closed by another agent as this is written.

## Findings

### docs-promise-the-pull-cannot-keep | high | The operator guide claimed the pull fills a fiscal ID it never adopts, closed at `299e1e988e`

Measured at `01decbae15`, closed at `299e1e988e`. The guide's "what the pull cannot
fill" section opened by stating that the pull fills the operator's fiscal ID, fiscal
address, postcode, and cadastral reference. `CENSAL_ADOPTABLE_PATHS` in
`src/cadrumo/application/user_profile/_censo_sync.py` is three paths -
`contact.fiscal_address`, `contact.postcode`,
`contact.fiscal_address_cadastral_reference` - and the fiscal identity is deliberately
absent from it. The projection emits the identity only so the ownership guard has an
input to compare; the reconciliation never adopts it. The campaign's own live run
recorded three adopted paths rather than four and said so.

Two things made this more than a wrong sentence, and the second is what took it from
medium to high.

The page contradicted itself eleven lines later, by correctly explaining that a pull
refuses a record whose fiscal ID is not the profile's - a refusal that is only coherent
because the ID is read rather than written. So the guide simultaneously claimed the
pull fills the ID and that it compares against it. A reader resolving that
contradiction has to already know the answer.

It reached an operator silently, and specifically the operator least able to notice.
The ownership guard deliberately allows the read through when the profile carries no
recorded identity, which is the ordinary first-read case. So someone following this
guide with a blank fiscal ID runs the pull, is told it succeeded, and the ID is still
blank - a documented promise failing with a success report, for a first-time user.

A second-order question this opened is recorded as raised rather than assessed, because
this review did not trace it: whether a profile carrying no recorded identity, combined
with a session authenticated as a different taxpayer, is a path to writing one
taxpayer's address onto another's profile in a bucket holding several. The finding
above is bounded at the documentation and its silent-failure consequence. The guard's
own safety is a separate question with a separate owner.

### populated-expectation-nothing-compares | high | The identity guard's expectation set is proven complete; the comparison consuming it has no test

Measured at `cbbe671fbf` and open there. `_assert_session_identity_matches_expected`
in `src/cadrumo/application/auth/_sessions.py` is called from four sites - lines 370,
449, 475 and 505 - and no test in the tree references it at that commit.

What exists is `test_every_provider_carries_an_expectation_for_the_session_check`,
which proves the expectation is populated for every member of the provider enum. That
is a real gate and it is not this gate. One proves the input to the comparison is never
absent; the other would prove the comparison refuses. Neither implies the other, and
the failure mode of having only the first is precise: a populated expectation that
nothing compares passes silently rather than skipping loudly, which is the same shape
as the defect the guard was added to fix.

The certificate provider is why this is more than a coverage gap. Every other provider
binds a comparable identity earlier, where an operator-configured credential can be
checked against the session. A certificate has no such credential, so the guard's own
docstring says the certificate case is checked there rather than exempted - and
"there" is the untested function. For that provider this is the only check.

The gate is to construct a session whose identity differs from the expectation and
assert the refusal, at the function rather than through a call site: a test driven
through one of the four call sites tends to exercise that site's plumbing and can pass
without the comparison ever disagreeing.

A note on how this was measured, because it changed the number twice. The working tree
at the time of writing shows three call sites and a test file that references the guard
thirteen times. Both readings are of uncommitted work: another agent is closing this
finding, and their test is untracked while their `_sessions.py` edit is unstaged.
Neither is visible at `HEAD`. The reportable measurement is the one taken from the
commit; the tree reading would have recorded this finding as already closed and the
guard as having one fewer call site than it has.

### explanation-accretes-third-instance | reserved | Owned by `censal-reader`, to land in this document rather than a second one

Reserved slot, not a finding by this reviewer. A third instance of the pattern already
recorded in this feature's tooling-honesty audit as
`explanation-accretes-where-the-reasoning-happened-not-where-the-hazard-is` was found
by another agent: one expression existing twice, once as a plain URL and once as a
registry lookup key, with the explanatory reasoning attached to the copy that merely
looks important.

Two coordination facts belong in the record. First, that instance's natural home is the
finding it extends, in the tooling-honesty audit, not this document - the audit template
makes findings a rolling log, and splitting instances one and two from instance three
across two audits costs a later reader the pattern. Second, the generalisation is that
agent's and is deliberately not restated here from a paraphrase; the reviewer requested
it in their own words, with the three destinations named, rather than reconstructing it.
This slot records that the finding exists and where it went, so its absence from this
document is not read as an omission.

### close-suspicions-unfounded | medium | Four suspicions carried into this review were checked and are unfounded

Measured at `01decbae15`. The commissioning brief named several things it expected to
be wrong. Four were checked and are not, and they are recorded as falsified for the
reason falsifications are worth recording at all: an unrecorded suspicion is re-opened
by the next reviewer, who pays the same cost to reach the same answer.

The operator guide is otherwise accurate. Beyond the fiscal-ID sentence above, its
account of adopted, unchanged and diverging outcomes, of the refusal on a foreign
record, of what the pull cannot reach, and of the certificate import's currently
refusing state all match the code.

The declarations module's comment already matches its refuse behaviour, corrected at
`e27261e554`. The suspicion was that it still described a degrade path.

The `P02.S06` no-write proof is a real gate, not a restatement of intent. It lives in
`src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_no_write_surface.py` and
fails closed at runtime on the filing-tool and procedure-launcher landings, keeping the
static string check only as the weaker of two walls.

`P02.S04` produced a concrete recorded artefact rather than a claim of discovery: the
consulta selectors are recorded, and the live-origin path has its own test.

### probe-no-session-claim-withdrawn | medium | The reviewer's own twice-repeated claim that the probes' no-session contract was untested is false

Measured at `01decbae15`. This reviewer told the coordinator twice that nothing tested
the readiness probes' no-session contract. It landed as `P01.S18`, and it landed
stronger than the reviewer had asked for:
`src/cadrumo/application/auth/tests/test_probe_survives_without_a_session.py` asserts
the profile read is *declined* rather than merely survived, on the reasoning that the
weaker form would false-green against a file-backed store.

The withdrawal is recorded rather than quietly dropped because of which direction it
runs in. Nobody was going to question this claim: it came from the agent who had
flagged the gap, it had been repeated, and the coordinator had accepted it. A stale
claim is hardest to catch when its author is also its only likely challenger, and the
persona switch is what produced the challenge - reading the tests cold, without the
memory of having reported them missing.

### verified-once-not-gated | low | `P03.S10`'s live evidence is real and is not a gate, permanently

Measured at `01decbae15`. The step's evidence is a live authenticated run against the
AEAT consulta, which recorded three adopted paths and the identity read-not-adopted.
That is genuine external evidence and it is the strongest evidence available for that
path. It is also not a gate, and cannot become one without a live session, which no
committed test may require.

This is recorded as a permanent property of the step rather than as a gap awaiting
closure. The distinction matters for a later reader deciding what to trust: verified
once by measurement is a different claim from enforced continuously, and a record that
does not separate them invites either mistaking the live run for a gate or dismissing
it as untested.

### deferrals-chosen-not-missed | low | Five items are deliberately open, with their reasons, so none is later read as an oversight

Measured at `01decbae15`. Written down, these are decisions; unwritten, each becomes a
gap nobody remembers choosing.

The capture-path read guard's host-set change is deferred pending an operator probe: it
turns on what AEAT actually serves, and the tree cannot answer it.

Five pinned readers surfaced by the host-pinning item were never individually assessed.
The item closed on the ones that were, and the remaining five are unmeasured rather
than cleared.

The regime facts - activity, tax regime, IVA regime, enrolment - stay operator-entered
because AEAT publishes no read-only surface carrying them. This is a property of the
authority's surface, not a shortfall of the reader, and it is the one deferral that
does not close by anyone's effort here.

`valid_to` is not consulted by the effective-dating work, so an expired window still
projects. The code says so at the site, deliberately: honouring expiry is a different
and better rule, and it was not in scope for making the projections consult window
order at all.

`_REQUIRED_PLACEHOLDERS` is guarded against the schema rather than derived from it. The
guard proves every entry is admissible without making the schema generate the set,
which was the narrower and reversible choice.

### review-found-less-than-its-brief-expected | low | The bottom line contradicts the framing the review was commissioned under, and is the entry a later reader will most doubt

Measured at `01decbae15`, twenty-two of twenty-three Steps closed. Of those
twenty-two, two carried claims this review could falsify, and neither is broken
behaviour. No Step closed on a ruling with nobody measuring. The campaign was in better
shape than its count of open items suggested.

This is recorded deliberately, in the form a reader can attack. A review that returns
little after looking is indistinguishable, from the outside, from a review that looked
little - and the incentive runs one way, because a long findings list reads as
diligence. The defence against that reading is not the conclusion but the method: the
two falsifiable claims are named with their commits, the four unfounded suspicions are
named so they need not be re-opened, the reviewer's own stale claim is withdrawn in
public, and the deferrals are enumerated with reasons. A reader who doubts the bottom
line has the material to re-derive it.

`P01.S23` is deliberately unchecked, and the reason is not that it is unfinished
bookkeeping. The post-auth navigation salvage is unverified pending a live run: a spent
second factor cannot be reproduced without one, so landed-and-tested is as far as the
tree can take it. The record should make it impossible to read that Step as verified.

### required-field-binds-for-nobody | high | A required field on a zero-row repeatable section is emitted for no taxpayer, and the obvious consumer of the fix crashes the validator

Open. Established by censal-sync building it twice and committing nothing; recorded
here because the implementing module was deleted rather than parked, so this text is
the only surviving record of a design that was proved correct.

Two independent blockers, either sufficient.

The first is that suppression can only subtract. Raw emission was measured across three
populations with the section repeatable:

    salaried              -> ['iva.regime']
    declares actividad    -> ['iva.regime']
    legal entity          -> ['iva.regime']

`activities.description` is emitted for nobody. The row loop finds no rows in a
zero-row section and produces nothing, identically for every taxpayer, so the
accidental protection over-spares: it also shields the taxpayer who declared an
economic activity and never named it, which is the case the gate existed to make
loud. A call-site filter can only remove entries from that set; delivering the missing
case requires an addition, which means changing the row loop itself. The scope is not
`activities` - it is every required field on every zero-row repeatable section, 13 of
the schema's 15.

The second is access, and it is a closed door worth naming because the wrong function
is the one a later author will find. **Do not consume `projection_for_taxpayer`.** It
passes every structural check: sibling module to `_completeness.py`, accepts the
mapping shape the validator already holds, import edge already allowlisted, docstring
claiming it is the canonical coercion path. It was adopted on those grounds and broke
five tests, because underneath it is a strict coercion that raises on any undeclared
token:

    ValidationError: 1 validation error for SetupAnswers
    output_language
      Value error, '__undeclared_probe_token__' is not a valid OutputLanguage

That input is a test deliberately feeding a bad token and expecting an issue to be
reported. Wired through the projection, the validator crashes instead of reporting, on
exactly the input it exists to catch. The principle generalises past this function: a
validator cannot depend on a strict projection of the data it validates, because its
input is untrusted by definition and a strict coercion assumes the opposite. Signature
fit is not contract fit - a strict coercion and a tolerant projection have identical
signatures.

The policy is inherited rather than reopened: required when the legally grounded
economic-activity predicate is not False, or when the entity is legal or attribution -
two arms, two reasons, routed through the existing predicate rather than a new one.
Blast radius measured at six fixture files.

The gate design is proved correct and should be rebuilt from this spec rather than
re-derived. Its anti-tautology arm, flipping the repeatable flag off in memory:

    salaried,           repeatable off -> not reported  (spares it)
    declares actividad, repeatable off -> reported      (charges it)

Blanket emission is wrong: `attribution_entity_socios`, `properties` and `usage_ratios`
are correctly silent when empty. Conditional emission needs a per-section applicability
predicate and the schema has no such key - its complete set is description,
effective_dated, enum_values, export_headers, fields, key, legal_refs, maximum,
minimum, model_selectors, nullable, repeatable, required, schedule_predicates,
sensitivity, title, type.

Precedent favours making the declaration bind rather than removing it: the enum-values
finding earlier in this campaign resolved the same shape by making them bind. The row
loop's silence on empty sections is a deliberate decision landed the same day, so
partially reversing it needs its own decision record rather than an amendment.

### multi-activity-capability-unscoped | high | The schema declares a repeatable section that nothing writes, reads by index, or models as a collection

Open, and a new capability rather than a fix. Established across two agents, entirely
by measurement.

Nine production surfaces across four layers address the section unindexed, with zero
indexed production usage. The index-dropping normalizer has exactly one production call
site and no consumer normalizes, so writing an indexed path today silently blanks the
readiness gate, the calendar enrolment check and seven CLI status sites - a missing key
reads as "not declared" rather than erroring. A taxpayer with two IAE epigraphs cannot
be represented through any surface.

The cardinality is authoritative, bounded, and confirmed by two artefacts of different
kinds. The bundled M036 diseño carries four numbered activity slots for each of two
casillas; its página 4 record is the primary activity register and maps one-to-one onto
the profile section; and the diseño's own worked example ships two page-4 records in a
single declaration. Separately, Orden HFP/1359/2023 states the rendimiento is the sum
of the rendimientos of each activity and that the procedure runs per activity. A form
layout and a legal text, produced by different processes, agreeing.

The projection trap is worth recording because both agents fell into it: the Renta
casilla asking for one epigraph is a projection over the row set, not evidence the
underlying fact is singular. A singular casilla does not imply a singular fact.

What the capability needs: a writer, since nothing writes indexed rows for any
repeatable section; index-aware readers replacing the nine flat lookups; a
collection-valued downstream model, since the deadlines profile constructs the epigraph
as one scalar; a principal-activity projection for the modelo that genuinely wants one;
and a field-set reconciliation rather than indexing alone - the diseño row is
(descripción, sección I.A.E., grupo/epígrafe, tipo de actividad) while the profile row
is (description, cnae, iae_epigraph), so two diseño fields have no profile home and one
profile field has no diseño counterpart.

Template: `src/cadrumo/application/aggregation/_atribucion_member.py:31` is a complete worked indexed reader
- it enumerates indexed paths, groups by row, checks required fields per row and stamps
per-row provenance. It has no writer, which is the same gap one section over. Do not
copy `src/cadrumo/application/user_profile/_cotejo_apply.py:83`: it is the only indexed writer that ships and it is
not a repeatable section, but an object-typed field carrying row structure through an
ad-hoc path convention with sub-fields undeclared in the schema. It works and it is the
wrong shape to generalise.

Three items are recorded as unverified and must not be inherited as done. The empirical
surface sweep is unrun - both agents swept literals with the same tool, which
corroborated rather than confirmed, and a reader reaching the values without naming a
path is invisible to both. The two-activity módulos calculation is unrun, so the
predicted false advisory on a correct filing remains inference. And two questions are
unanswered: whether the other renta modelo's estimación-objetiva section shares the flat
shape, and whether any módulos unit slot is genuinely shared across activities - the
second changes how a per-activity model should be shaped rather than whether it is
needed, so it belongs before design.

The per-activity precondition is already recorded in the code at three revision
predicate sites and at the profile schema, with the órden quoted and the reason it is a
note rather than a gate, so this scoping need not re-derive it.

### marker-gate-red-across-four-campaigns | medium | A gate went red and stayed red because nothing runs it before a commit, and its sister check fires on ordinary English

Open and not this campaign's to remediate. Established by the lead, refined here.

The pytestmark-placement check is red with four violations, one per active peer
campaign. A hypothesis that the gate arrived red in a tree-wide rename was tested and
falsified: none of the four files existed at that commit. The gate was green and four
campaigns each broke it, three of them landing after the first violation - and a
campaign adding to an already-red gate cannot distinguish its own breakage from the
standing red, which is how a red gate becomes self-sustaining.

The attribution method is worth keeping. Last-touching commit identifies who last wrote
a file, not who introduced a violation, and the shared git identity cannot discriminate
agents at all. Here the add-commit is decisive because all four files were created
after the gate existed, so whoever added the file added the violation. That is stronger
than blame and it is why this attribution can be trusted where a last-touched one could
not.

Why it went unnoticed, measured: this worktree has no pre-commit hook. The hooks path
holds only post-phase git-lfs hooks and there is no pre-commit configuration, so a gate
is red only where somebody happens to run it.

The refinement changes what the finding is. The sister check bans a bare token that is
also ordinary English, and this agent tripped it with a docstring using the word in its
normal sense about an hour after another campaign had cleared its own violation from
the same check. The fix was to reword a docstring, not to remove campaign metadata,
because there was none to remove. **A gate whose remedy is rewording rather than
correcting trains authors to write for the gate instead of the reader**, and that
belongs with its owner alongside the four placement violations. It also explains a
stale count: a number describing a shared ratchet has no owner, so nobody re-derives it
in transit - the file list is attributable, the count is not.

### composition-reproduction-ran-and-did-not-reproduce | medium | The guards are inert as reported; the composition is harmless for a reason nobody had stated, and the original framing was too strong

Closed by execution after being carried as unverified. The unexecuted half was run,
and it did not reproduce - which is a result rather than a non-event, because what
stops it was not any of the three defences built for it.

The guards are inert exactly as measured. For the certificate provider the credential
guard returns before its blank check, having no operator-configured credential to
compare, and the deferred session comparison admits because the expectation it would
compare against is derived from the very field that is absent. Both halves executed;
that stands.

What was never true is the implication drawn from it. The reproduction established, by
tracing all three call sites, that the ownership guard's `incoming_identity` comes from
the READ and never from the session - `apply_censal_read` passes the read's identity,
and so do the file-ingest and manager-action call sites. **The guard compares the
profile's recorded identity against the identity in the document; the session's
identity is not an input to that comparison at any point.** So a certificate session
bearing another taxpayer cannot by itself cause that taxpayer's data to be adopted.
What would have to happen is that the read comes back describing them, which is
precisely what the guard refuses.

The certificate provider's role in the original finding was therefore real but
**indirect**: it explained why no expectation existed for the deferred auth check, not
a channel by which a foreign identity reached the adoption. The finding's guard-level
claims survive; its composed severity does not, and this entry supersedes the stronger
reading rather than quietly narrowing it.

Two things this leaves. The property is load-bearing and undeclared, which is the same
shape as the accidental protection recorded elsewhere in this document - so it is being
pinned by a test rather than left as an incidental consequence of how the parameters
are wired. And the honest sequence is worth keeping: the claim was flagged unverified,
survived as an unchecked step rather than decaying into an assumption, and was retired
by being run. The disclosure did its job; the run is what settled it.

### rulings-overturned-by-their-own-evidence | medium | Three decisions were reversed by measurement after being ruled, and the reversals share a shape

Recorded because the reversals are more instructive than the rulings.

A schema flag was going to be stripped as incorrect until the M036 diseño falsified the
premise underneath - that a singular casilla implies a singular fact. The evidence that
settled it was a document neither party had consulted, not better reasoning about the
document they had.

A new predicate was ruled and withdrawn when a third shipped implementation was found
under a name nobody had searched, legally grounded and three-valued where the ruled one
was two-valued. That is the second time in this campaign a concept already existed under
an unsearched name.

A gate was cleared to implement and then proved undeliverable by building it, with the
implementing work discarded. The build was the measurement.

The shape they share: each ruling was sound on the evidence held at the time, and each
was overturned by an artefact rather than by an argument. **When a conclusion rests on
one authoritative document, the second reader's job is to find a different document, not
to re-read the first.** Agreement reached by the same route is corroboration, not
confirmation.

### method-findings-worth-carrying | low | Four generalisations that outlived the findings that produced them

An anti-tautology arm proves a guard would fire given its input; it cannot prove
anything supplies that input. A gate can compile, pass its own mutation proof, and be
wholly inert because nothing upstream hands it the path. Pair every "given X the guard
refuses" with "given the real upstream, X arrives" - write the expected-fail case.

Signature fit is not contract fit. A strict coercion and a tolerant projection have
identical signatures, and the structural checks that normally establish suitability -
module location, accepted type, allowlisted import edge, a docstring claiming
canonicality - were all satisfied by the wrong function.

A magic value in a selection is a decision that needs a stated criterion. A `-1` index
chooses an element; which element, and why that one, is a rule that belongs written down
rather than implied by the subscript.

The two semantic indexes have independent health, so unavailability must name which one.
One reported a terminal successful state at a handful of sections while the other was
fully usable; a blanket refusal would have wrongly blocked the decision search that
resolved a real blocker. A terminal state is worthless evidence either way - only
section count against tree size means anything.

## Recommendations

Separate proving an input is populated from proving the consumer refuses, wherever a
guard has both halves. The identity-guard finding is the worked instance and the
generalisation is cheap to apply: for any check whose input is supplied by a
completeness gate, ask what fails if the comparison itself is removed. If the answer is
"the completeness gate still passes", the comparison has no gate. Prefer testing such a
comparison at the function over driving it through a call site, because a call-site test
can pass while the comparison never disagrees.

Bind an operator-facing claim about what a surface writes to the collection that
decides it. The documentation finding closed by tying the sentence to the adoptable-path
tuple, which is the right shape: prose that enumerates a set drifts from the set, and
the drift is invisible because both halves read as correct in isolation. Where such a
sentence cannot be mechanically bound, the cheaper discipline is to write it as a
consequence of the named collection rather than as an independent list.

Weigh a guard's deliberate permissiveness against the documentation that surrounds it.
The ownership guard's allowance for a profile with no recorded identity is correct for
the first-read case and is exactly what made the wrong sentence silent. A guard that
passes by design in the beginner's case will not surface a documentation error to the
beginner, so prose describing such a path carries more weight than prose describing a
path a refusal protects.

Record falsified suspicions with the same care as findings, and in the same document.
Four checked-and-unfounded items are recorded above for a reason that generalises past
this campaign: the next reviewer inherits the same suspicion from the same source, and
without the record pays the same cost to reach the same answer. This is the cheapest
finding class to produce and the easiest to omit, because it feels like reporting that
nothing happened.

State whether evidence is a measurement or a gate, every time, and treat once-verified
as a permanent property where a gate is impossible. Live-session evidence cannot become
a committed gate, so a record that files it as an open gap generates work that can never
close, and a record that files it as verified invites a later reader to assume
continuous enforcement. Naming which it is costs a clause.

Measure a claim at the commit, not in the tree, before persisting it - and do it again
at persistence time rather than at authoring time. This review's own numbers moved
twice inside one document: a finding closed between the review and its persistence, and
another finding's call-site count read one lower in the tree than at the commit because
its fix is in flight as untracked work. Both would have been recorded wrong from a tree
reading. The discipline that catches it is one command per claim, and the interval it
protects against is the interval between finishing a record and committing it.

Persist a campaign's honesty review as a document at the moment it is produced, not
after. This review existed only as chat for a day, which put every entry above one
session-boundary away from being lost - and the deferral list is the part that would
have been lost most expensively, because a chosen deferral and a missed one are
indistinguishable once the reasoning is gone.
