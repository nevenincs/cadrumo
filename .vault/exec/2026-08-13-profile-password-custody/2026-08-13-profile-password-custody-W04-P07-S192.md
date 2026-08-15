---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:5d9da1171fe6c432e9300e096682fb9dded273964b40554870ed4b80b63e9a76'
step_id: 'S192'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh narrow the persisted command event onto the closed bucket-event enum across all four of its sites in one change, since the record model is strict so an enum field refuses even a valid member's raw string value and every construction must pass a member in the same commit or the tree refuses every profile-record write, the durable bytes being byte-identical either way because the command event is never serialised and the shape that reaches disk is already typed, and retire in the same action the comment that describes the gap as pending

## Scope

- `src/cadrumo/application/user_profile/_capsule_record.py and _profile_record_repository.py and tests/_profile_record_boundary_support.py and src/cadrumo/application/profile_custody/__init__.py`

## Description

- Re-verify the four construction sites and the model field at head before
  touching anything.
- Narrow the command witness field onto the closed bucket-event enum and
  convert all four constructions in the same change.
- Delete the event-type lookup arm the narrowing makes unreachable.
- Retire the comment and the docstring paragraph that describe the gap as
  pending.
- Promote the port protocols the custody-ports package reaches for onto the
  owning package's facade and rewrite the consumer onto it.
- Prove the boundary bites against a real published capsule from outside the
  tree.

## Outcome

**THE FOUR SITES WERE RE-DERIVED AT HEAD, NOT TAKEN ON TRUST, AND THE COUNT
WAS RIGHT.** The field carried a bounded string one to a hundred and
twenty-eight characters wide. Three constructions passed a member's `.value`
-- the capsule creation event, the setup-completed event in the record
repository, and the replacement event in the shared boundary-fixture support
module -- and the fourth passed a local name already narrowed to a member one
statement earlier. A tree-wide walk for the constructor confirms four and only
four; the type is referenced in three further places as a parameter
annotation, which construct nothing and needed no change.

**THE PREMISE WAS MEASURED BEFORE THE EDIT RATHER THAN AFTER.** A probe run
against head first recorded what the field then accepted: the member, the
member's value, AND a bogus string, all three admitted, with the bogus string
surviving to be refused deep inside the event builder. That is the state the
narrowing removes, and recording it first is what makes the after-measurement
a comparison instead of an assertion.

**THE NARROWING AND ALL FOUR CONVERSIONS LANDED TOGETHER.** Under this model's
strict configuration a closed-enum field refuses a raw string even when the
string is a valid member value, so any partial version refuses every profile
record write. The field is now the enum, three sites pass the bare member, and
the fourth passes the already-narrowed local. Nothing on disk moved: the
command witness is never serialised, and the durable event it becomes already
carried the closed type, so the digest preimage takes the same token it always
did. No version bump, no upgrader, no fabricated old-version fixture.

**THE ARM THAT BECAME UNREACHABLE WAS DELETED, AS ITS AUTHOR EXPECTED.** The
event builder's first arm coerced the event type and refused when the coercion
failed. With the field closed, the value arriving there is already a member and
that coercion can no longer fail, so the arm and its local are gone and the
builder passes the command's own type straight through. The second arm, split
out by the earlier row so an unparsable instant stops reporting itself as a bad
event type, is untouched and still bites -- the probe drives it and requires
its message to name the instant and NOT the event type. The count-versus-key
refusal split by the other closed row in the same module is likewise untouched.

**TWO PIECES OF PENDING-STATE PROSE WERE RETIRED, NOT ONE.** The row named the
inline comment, which said the event travels onward as a plain string through a
model that accepts any string and that the catching coercion lives inside the
writer. Reading the surrounding function turned up a second statement of the
same false claim: the public docstring of the fact-changes command told callers
that the capsule writer coerces whatever reaches it and refuses the whole
command when that fails. Both now describe the closed type. The early narrowing
itself was KEPT and its remaining justification stated: the command witness is
composed after the record load and the compare-and-swap, so the call-site
narrowing still refuses an untyped caller strictly earlier than the model
would.

**ALL EIGHT PORT PROTOCOLS WERE PROMOTED, AND THE JUDGEMENT WAS PER SYMBOL
RATHER THAN A BLANKET UNDERSCORE STRIP.** The custody-ports package reached
into another package's private module for its protocols. Every one was tested
against the same question -- is this a genuinely shared primitive, a single
caller's narrow view, or a design defect to remove -- and every one answered
the first way for the same concrete reason: each appears in the PUBLIC
signature surface of the consuming package's own exported API, so a consumer of
those functions cannot annotate against them at all while they stay private.
The bucket-session port is the parameter or return of six exported functions.
The envelope and sentinel ports are fields of two exported frozen dataclasses.
The password-material port is a return and a parameter of the load and unlock
doors. The secure-object repository port is what the exported repository
context manager yields. The persisted-session port spans the mint, advance and
type-guard trio. The session-resume outcome port is the resume door's return.
The recovery-envelope port, which a concurrent owner added to the same import
block mid-row, is a field of a newly exported enrollment dataclass and a
parameter of an exported function -- the identical shape, so it was promoted on
identical grounds rather than left dangling.

**THREE PORTS IN THE SAME PRIVATE MODULE WERE DELIBERATELY NOT PROMOTED.** The
raw-row and record ports are referenced only inside the repository protocol's
own body, where they resolve in their defining module's namespace, and no
cross-package consumer names them. Exporting them would be speculative surface,
so the promotion is exactly the reach and not the module.

**THE BITE-PROOF RUNS ENTIRELY FROM OUTSIDE THE TREE AND FORTY-SEVEN
ASSERTIONS PASS.** The structural half reads each construction's event-type
argument out of the AST rather than matching file text, because one module
holds two of the four sites and a text needle cannot tell them apart; it pins
the site count so a new unswept construction is visible, and requires no site
to read a value attribute. That sweep is proved non-vacuous by a negative
control that reinstates the old shape IN MEMORY -- first at one site, then
independently at the other -- and requires exactly one flag each time, with the
file on disk re-read afterwards and asserted unchanged. The runtime half drives
a real published capsule with a real SQLite substrate and real encryption: the
member is accepted and stays a member, the member's value and a bogus string
and an empty string are each refused, the refusal leaves the persisted
revision, its row revision token and the event history byte-identical, and a
member then drives a real replacement through to revision two with exactly one
event appended carrying the closed member and the unchanged durable token. The
facade half resolves every promoted protocol off the public boundary and
asserts each IS the owning module's object rather than merely something of that
name, then walks the whole exported surface for a name that does not resolve --
the boundary states the same truth in three hand-synchronised places and warns
about exactly that class of slip.

**THE LIFECYCLE WAS UNIMPORTABLE MID-ROW FOR SOMEONE ELSE'S REASON, AND THE
PROOF WAS ROUTED AROUND IT RATHER THAN WEAKENED.** A refusal class reached the
tree with no error-code registry entry, which raises at class-definition time
and so took down the capsule lifecycle import chain tree-wide. It was reported
rather than absorbed, and the capsule proof was rebuilt on the record store's
own production create path aimed at the canonical bucket database file, so the
later replacement operates on the very same capsule. The gap is now closed at
head: the class is declared with its own dedicated message key resolving to
real prose in all four locales, and the chain imports again.

**THE FIRST REPORT OF THAT GAP NAMED THE WRONG OWNER. THE MECHANISM THAT MADE
THE WRONG ANSWER LOOK CONCLUSIVE IS THE PART WORTH KEEPING.** The unregistered
class was traced to the commit that introduced it, that commit's subject line
carried another row's identifier, and the defect was reported to that row's
owner. The owner had run no git write at all.

The inference failed because of how commits are actually produced in this
shared worktree. A bare commit stages whatever is in the tree, so ONE commit
routinely contains the uncommitted work of SEVERAL agents at once, and it
carries the single subject line its author typed -- naming that author's own
row and no other. This commit is the worked example: nine files, of which five
are exactly THIS row's uncommitted change set (the facade redirect, the port
promotions, and the command-event narrowing across three modules), two are the
accused row's, and two are shared test-support modules belonging to neither.
The subject named only the accused row. Compounding it, every commit in this
worktree carries the same git author, so `git log` authorship cannot separate
any two agents either.

So neither the subject line nor the author field is evidence of who wrote a
given hunk, and the two most reachable signals are both misleading in the same
direction: they point at whoever typed the commit, for changes they never made.
What does discriminate is FILE OVERLAP against the reporting agent's own known
edit set, and TIMING against when each agent's tree was dirty. Read a diff hunk
by hunk against the ownership map before naming anyone.

The cost was real and asymmetric: the accused owner lost a session to a defect
that was already fixed and escalated for permission to fix it. The same
inference error was made independently by another agent on the same day against
a different target, so this is a property of the tree rather than one agent's
carelessness. Left uncorrected it would have hardened here, in the durable
record, long after the conversation that could have refuted it was gone.

## Notes

**THE SUITE IS GREEN WHERE THIS ROW REACHES AND RED WHERE OTHERS DO.** The
user-profile and custody suites report three hundred seventy-nine passed and
fourteen failed over a twenty-three minute sequential run. Every module this
row touches passes: the capsule-record suite, the in-process record roundtrip,
the cross-process record roundtrip and the custody roundtrip are all green. The
fourteen are the ambient defects already named -- the registry authority
refusing to load, a fixture helper's signature drift, and the profile-lifecycle
and CLI-surface collisions -- plus peer CLI work in flight. The decisive
attribution is not that list but its complement: the whole run's output
contains no occurrence of the command-event type, the command witness class, or
the record integrity refusal, so nothing in it touches the surface this row
changed.

**TWO TREE-WIDE GATES ARE RED AND BOTH WERE ATTRIBUTED BY MEASUREMENT RATHER
THAN BY ARGUMENT.** The re-export baseline gate names nine packages including
the one edited here, which looked like a candidate. Reading the gate showed it
counts only TOP-LEVEL relative imports, and the change here sits inside a
type-checking block; running the gate's own collector over head's bytes and the
working tree's bytes for all five touched files returns identical finding sets,
twenty-four against twenty-four for the custody-ports package and unchanged for
every other. The eager-import gate fails on the bare landing surface pulling in
the workflow package and the whole registry; tracing every importer of that
chain through the real landing invocation returns not one module inside either
package this row touches. Both are pre-existing and belong to other owners. The
import-hygiene test-debt failures list thirty-two reaches, none of them in a
file this row edited.

**THE PRODUCTION HALF OF THE HYGIENE FAMILY IS NOW EMPTY.** The scan reports
zero production files carrying a cross-package private import and zero symbols
needing facade promotion. The remaining count in that family is entirely
test-only debt owned elsewhere.

**COLLECTION IS AT PARITY ONCE THE CONCURRENT WRITES ARE ACCOUNTED FOR.** The
pre-change baseline collected twenty-five thousand eight hundred eighty-three
of thirty thousand three hundred twenty-three clean. Afterwards the run errors
in modules this row does not touch, and the loader states its own cause: the
registry directory changed during cache fingerprinting while a concurrent
authority sweep was writing. A second run moved the errors to different
unrelated modules, which is the signature of the write race rather than of a
regression. The modules in scope resolve throughout, at two hundred ninety-five
collected items.

**A PEER'S BROAD COMMIT CONSUMED THIS WORK BEFORE IT WAS REPORTED, AGAIN, AND
IT IS THE SAME COMMIT AS THE ONE ABOVE.** Nothing was staged or committed from
this session. Mid-row the working tree went clean for every file here while the
content remained correct at head: one bare commit captured the field narrowing,
all four conversions, the deleted arm, the retired prose and the facade
promotions, and it is precisely the commit that carried the unregistered
refusal class and another row's subject line. Only the eighth port's promotion,
added afterwards, remained uncommitted at report time, and it too was swept
before the row closed. The content is verified present and both probes re-run
green against the current head; what is lost is the attribution.

**THE STANDING HAZARD IS NOT THE LOST CREDIT, IT IS THAT NOBODY CAN READ THE
HISTORY.** A bare commit merges several agents' trees under one row's subject,
and because every commit here carries the same git author there is no signal
left to separate them. That has now produced two distinct failures in one
campaign: work delivered under another row's name, and a defect reported to an
owner who did not write it, costing that owner a blocked session and an
escalation over something already fixed. Reading a commit subject as evidence
of authorship is what made the second one, and this row made that mistake.

**TWO FORMATTER-DRIFTED FILES IN THE SAME PACKAGE WERE LEFT ALONE.** The
formatter would rewrite two test modules there. Both are clean against head and
neither was edited here, so the drift is another owner's and was reported
rather than absorbed.
