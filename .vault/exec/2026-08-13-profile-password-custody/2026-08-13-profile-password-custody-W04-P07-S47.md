---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:bc1b77f385d033533b8edd240eb57968e652e4261f0789bc62516dd11617aacd'
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

Five gates were proven to bite through patches applied from outside the
repository: the injected dead instruction, the stale exemption, an enrolled
spelling whose verb is live again, a policy row for an unregistered path, and
a stale module entry in the policy walk. The first probe surfaced a real
robustness defect on the way -- a display-path computation raised on a file
from outside the tree, so a probe could crash the scan instead of failing it.
Reporting was made path-agnostic; whether an offender is reported must never
depend on how its name renders.

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
