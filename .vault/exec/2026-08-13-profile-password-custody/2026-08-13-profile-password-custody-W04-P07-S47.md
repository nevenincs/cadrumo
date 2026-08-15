---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:dbf85c23ffe4179069a1ab545e39697e06f979655f0ccb0b4adfb154d56addc8'
step_id: 'S47'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make a dead operator instruction structurally impossible by enrolling the retired custody verb spellings in the scan that already walks source, the four catalogues, the documentation and the sequence contracts, after sweeping the sixteen surfaces that still cite them including a whole protect-data-access workflow and the repair-policy inventory

## Scope

- `src/cadrumo/entrypoints/cli/tests/ and docs/how-to/ and src/cadrumo/application/repair_integrity.py`

## Description

- Establish by invocation which spellings actually fail to resolve, and
  separate the ones an accepted ruling retired from the one whose absence
  nobody ruled on.
- Delete the six repair-policy rows and the two profile-bundle rows governing
  command paths the live command tree does not register.
- Bind the repair-policy inventory to the live tree in the direction that
  matters: no policy row may outlive its verb, derived, with nothing listed.
- Repair the coverage gate's own staleness so a deleted module fails as drift
  rather than erroring from inside the coverage assertion.
- Rewrite the protect-data-access workflow around what the product does, and
  delete the six sequence contracts whose commands do not exist.
- Re-found the five subgroup-help rows that had stopped asserting anything
  about secret handling once their verbs went unregistered.
- Enrol the two genuinely retired spellings, give every entry and every
  exemption a stated reason, and anchor both so a stale one fails.
- Give the shipped declared-unimplemented register the reverse arm it lacked,
  so a held declaration cannot outlive the gap it records, and assert a stated
  reason on every entry rather than on the one pinned by name.

## Outcome

The premise of the row did not survive contact with the tree, and the
correction is the deliverable.

Two derived scans already exist and already bite. One resolves every cited
invocation in the documentation and the sequence contracts against the live
command tree; the other does the same for production string literals, the
curated operator help and the four catalogues. Both were red at HEAD on
exactly these citations. The class was already structurally closed wherever a
citation carries the executable token. A spelling list added beside them would
have been the weaker of two mechanisms guarding the same ground.

The real hole is the citation that carries no executable token. Both derived
scans anchor their extraction on it, so neither can see a bare command path.
The repair-policy inventory is exactly that shape: an operator-facing catalog
of command paths written without the prefix. Eight rows sat there governing
verbs the tree does not register -- the six retired custody paths plus two
profile-bundle paths that were never implemented -- while every prefixed
citation of the same verbs was already failing. That inventory is now bound to
the live tree by a property, not a list, so a future retirement is caught
whether or not anyone remembers the gate exists.

The list survives for the remainder, narrowed and anchored. Its entries now
carry a reason each, its exemptions are keyed by path and enclosing function
with a stated reason each, and two anchors make a stale entry fail: one
asserts every enrolled spelling still names a path the live tree refuses, so
re-mounting a family forces the entry out rather than letting the scan forbid
a verb the product ships; the other asserts every exemption still matches a
real citation.

**The list's own failure mode reproduced during the work, inside the
deliverable.** The scan read raw file text, and a locale catalogue folds a long
string across source lines, so a two-word command path straddling a newline
read as clean while the derived catalogue gate -- which loads the YAML -- had
already flagged it. Three offenders were reported where four existed.
Collapsing whitespace for catalogues closed it, and the episode is the
concrete argument for preferring the derived shape wherever the token is
present.

**The sharpest finding is that one spelling is not retired at all.** The
passphrase family does not resolve, but no ruling removed it: credential
rotation is absent from every layer, and a deliberately-failing assertion
elsewhere in the command-line tests exists precisely to keep that visible.
This module asserted the opposite -- that the family was retired -- so two
gates in the same ownership encoded contradictory rulings on one verb and the
tree could never be green on both. Enrolling it would have laundered a missing
capability into a retirement behind a scan name. It is excluded, the exclusion
is stated where a future author will read it, and the contradicting assertion
was withdrawn rather than the deliberately-red one deleted.

The enrolment landed honestly green. Every offender the enrolled scan can see
was cleared: the ones in reach directly, and the four catalogue leaves by the
owner of the catalogues, who rewrote the refusal to state that a forgotten
passphrase cannot be reset while this step was in flight.

Seven gates were proven to bite through patches applied from outside the
repository: the injected dead instruction, the stale exemption, an enrolled
spelling whose verb is live again, a policy row for an unregistered path, a
stale module entry in the policy walk, a schema declaration held for a verb
that resolves, and a held declaration whose reason says nothing. The first
probe surfaced a real robustness defect on the way -- a display-path
computation raised on a file from outside the tree, so a probe could crash the
scan instead of failing it. Reporting was made path-agnostic; whether an
offender is reported must never depend on how its name renders.

## The split has a home, and it is not prose

The distinction this step drew was recorded as needing a first-class
representation. That conclusion was wrong: the representation already ships,
at two granularities, and the correction is worth more than the original
claim.

At the leaf, a register of command keys whose schema is declared while the
verb is knowingly absent holds five entries, each with a prose reason, and
its own docstring states the rule almost verbatim -- a capability removed
without a decision is a defect awaiting one, not residue of a retirement
someone executed. At the family, a mount-state on the operator-surface
contract carries the same idea with staleness teeth in both directions. The
passphrase family now declares itself unimplemented there, with a reason, and
the crash that opened this question is resolved without asserting a
retirement.

The two registers are not interchangeable and the difference decides the
passphrase case. The leaf register holds keys whose LEAF was declared and
whose verb went away. There is no passphrase leaf key at all -- the schema
universe carries two hundred and ninety-two keys and none of them names it --
so there is nothing for the leaf register to hold. The gap is a family-level
absence, and the family-level declaration is exactly where it belongs. It
should not be moved.

**Held is not citable, and collapsing the two would be the costlier error.**
The leaf register's own exposure predicate already rules it: a held key is
never operator-callable, because advertising a surface whose verb does not
exist hands an operator an instruction it cannot recover from, and the
declaration keeps the gap visible in source without putting a dead surface on
the wire. So the three states matter to DECLARATION surfaces -- schema
registers, family contracts, the catalogue keys backing a verb's own strings
-- where held must be kept. On CITATION surfaces -- documentation, refusal
text, next-step builders, suggestions, policy inventories, the agent harness
-- held and retired are the same thing: both are dead operator instructions.
The two derived citation gates already implement that rule by resolving
against the live tree with no held exemption, which is correct and must not be
relaxed to consult the register.

That answers the locale dimension without inventing anything. A catalogue key
whose namespace maps to a family declared unimplemented is orphaned-pending-
capability: it is neither dead nor live, and it must not be pruned. The
disposition is derivable from the family declaration rather than from a vault
note or a judgement call, which is what the parity repair needs.

The register was missing the half that makes it trustworthy. Its exit
condition -- restoring the verb removes the entry -- lived in prose only,
which is a request rather than a gate, and only one of its five entries was
asserted at all. A restored verb would keep its declaration, stay withheld
from the operator-facing surface by a note describing a closed gap, and stay
exempt from the coverage gate that could now watch it. The reverse arm and the
per-entry reason discipline are now asserted, derived from the live tree,
with no list of their own -- the same shape given to the spelling list earlier
in this step, and the arm the family-level register already had.

## Notes

The row's own count was wrong in both directions and is not repeated here. The
measured set at the start was fifteen files, of which nine were reachable.
Several moved under the step: the catalogues were swept by their owner
mid-flight, and one of the four locale citations had already gone before the
first census, which is why an early reading of three was itself understated.

The protect-data-access rewrite is a real narrowing and is recorded as one. The
page described recovery-key enrolment, verification, rotation, forgotten-
passphrase recovery and passphrase change. None of those commands exists, so
the page was handing an operator a false assurance at the worst possible
moment -- someone reading it believed they held a recovery key. The
replacement states the truth: the passphrase is the only key, there is no
command to change it and none to recover without it, so store it accordingly.
That deletes the last user-facing description of a custody capability the
product has lost, and the ruling on whether per-profile recovery returns is
still open on its own row. The page must be rewritten again when it lands.

The three development ledgers under the quality tooling still carry fourteen
entries naming these paths. They are not operator surfaces and are not in the
enrolled scan's corpus, which walks the shipped source, the catalogues, the
documentation and the contracts. Extending the corpus to reach them would have
made the gate red on arrival in files this step does not own, which is how a
gate gets weakened rather than met. They are handed back with exact locations.

The live walk added to the policy gate found four registered commands that are
policy-relevant and carry no row. They are invisible to the coverage direction
because it discovers from a hand-maintained module list rather than from the
tree. That is a second, separable defect in the same file and is not what this
step delivered; changing the coverage denominator would have demanded policy
judgements on four unrelated surfaces.

**Three independent surfaces were each one step from silently encoding this
retirement, and none of them consulted the register that exists to prevent
it.** A grammar gate asserted the family retired; an operator-surface family
declaration crashed the manifest as an orphan, whose only obvious repair was
deletion; and a catalogue carried keys whose only obvious repair was pruning.
Three different owners, three different mechanisms, one product decision
nobody took, and each route to it looked like tidying rather than deciding.
That recurrence is the argument, stronger than any single case: the missing-
capability state is load-bearing enough that a surface which cannot represent
it will manufacture a retirement under pressure to go green. The family-level
declaration gained its mount-state during this step for exactly that reason.
The remaining question -- which surface authoritatively declares a verb's
existence and how the others derive from it -- is open on its own row, and
this recurrence is the evidence for it.

A characterisation carried in an earlier record is superseded and must not be
inherited. Four further failures in the command-line lifecycle module were
described there as instances of an open product ruling, deliberately not
fixed. A later accepted ruling settled scripted profile creation and retired
the tests that assumed it, so only the passphrase assertion in that module is
genuinely held open; the rest are ordinary settled red awaiting their own row.
Preserving them as held would manufacture exactly the false hold this step
exists to prevent, in the opposite direction.

All of this step's work was committed by peers' broad sweeps rather than by
this session, which committed nothing. Two commits captured it, one of which
named the retirement in its subject. Nothing was lost, and the result was
verified against the tree afterwards rather than assumed.

The documentation build is red for an unrelated reason: the concurrent
registry campaign retracted export layouts across nineteen modelos, and
registry validation now fails inside the build extension. Sixteen of that
module's tests pass, and the sequence golden suite fails from the same cause.
The sequence inventory gate, which is the one that governs this step's
deletions, is green.
