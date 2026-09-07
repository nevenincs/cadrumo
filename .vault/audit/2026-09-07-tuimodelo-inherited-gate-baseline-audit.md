---
tags:
  - '#audit'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:c8698e7acd49dddc1b6ba16dadb6e1dd2ee7d3e033f872cf205baf759d0fce41'
related:
  - "[[2026-09-07-tuimodelo-plan]]"
---

# `tuimodelo` audit: `the gate state this campaign starts from`

## Scope

Eight gate failures were measured before this campaign changed anything, so that a later wave
meeting a red can tell an inherited one from a regression it caused. Each entry names the gate, the
exact failing subject, and who owns it. Anything not listed here and failing later is this
campaign's until proven otherwise; anything listed here stays another lane's until that lane fixes
it.

The record is deliberately a measurement rather than a promise. Several entries were re-measured
during execution and two of them proved load-bearing: one was mis-stated by a step's own premise,
and one changed the shape of a fix.

## Findings

### size-budget | critical | Three subjects exceed their declared ceiling, two of them files this campaign must edit.

The size ratchet is the only per-push blocking gate among these, so it is the one a later wave will
meet first. Three subjects fail. Two are files this campaign edits directly, which is why the
failure matters rather than merely existing: the verification-actions module and the
amendment-revision callable both sit above their own recorded ceilings. The third belongs to
another lane entirely, a locale coverage test.

The remedy is fixed by a peer decision and must not be re-litigated: the ceiling is never raised.
A subject over its ceiling is split or extracted. The ratchet additionally fails on a ceiling that
outlived its subject, so a module that shrinks below the default must have its entry deleted rather
than lowered; that arm fired during this campaign and is recorded in the step record that met it.

### canonical-authority-fixed-point | high | The destination authority is already violated, which the reachability wave inherits.

The workspace fixed-point gate reports eight canonical-authority violations for the declared
destination identifiers, being one duplicate authority definition, three indirect symbol consumers,
one indirect export, and three more across the owning test module. The subject module is unmodified
in the working tree and belongs to the navigation lane.

This one is called out beyond its own failure because a later wave in this campaign admits
destinations into that same closed alias and route table, under an obligation that the admission,
the route table and the count assertion land together. That wave does not start from a clean
authority, and planning it as though it did would misread the first failure it sees.

### cold-start-contract | medium | The contract fails on an unrelated verb and aborts before reaching later ones.

The cold-start refusal contract fails on the work-creation verb with a profile capsule that cannot
be identity-anchored. The failure matters structurally as well as individually: the contract
iterates verbs and asserts inside the loop, so it stops at the first failure and never reaches the
verbs after it. A verb added to that contract therefore gets no evidence from it until the earlier
failure is fixed, which is why one step in this campaign proved its own case by direct dispatch
instead.

### profile-session-resume | medium | Two failures, one of which asserts a shape the product no longer emits.

The session-resume suite fails twice. One failure reads an empty event-history catalogue. The other
is more useful than its failure: it asserts a refusal document nested one level deeper than the
product now produces. A test written in this campaign initially copied that stale shape and
reported a regression that does not exist, so the entry is recorded as a hazard and not only as a
red.

### object-names | medium | A standing burndown, already red and shrinking.

The object-name audit exits non-zero with several hundred enforced findings and a larger advisory
set. It is another lane's burndown rather than a defect this campaign introduced, and the count has
been falling. Work here adds to it only if a new public name collides; that was checked when this
campaign split a module and added public names, and it added none.

### import-contracts | medium | One contract broken by two application-layer edges.

The import linter reports one broken contract of the set, violated by two edges from the
application layer into an adapter and into the language-model package. Both files are unmodified
here. Both are subjects of this campaign's own migration wave, so the entry doubles as a record
that the wave starts from a known-violated boundary rather than a clean one.

### formatting | low | One unrelated module is unformatted.

The formatter reports one file needing reformatting, in a ledger test module this campaign does not
touch.

### source-plan-structure | low | Three rows in a source plan carry malformed scope clauses.

Three rows of the modelo interface plan fail structural validation because their scope clauses are
not wrapped and terminated as the schema requires. The consequence is operational rather than
cosmetic: the owning plan verb refuses to round-trip such a row, so two of them could not be
annotated when this campaign annotated every other open row, and their dispositions had to be
recorded in a step record instead.

## Recommendations

Treat this record as the attribution baseline for every later wave. A red not listed here is this
campaign's to explain; a red listed here is not, and the burden shifts only when the owning lane
has fixed it.

Re-measure rather than trusting an entry when a fix depends on it. Two entries here were already
refined during execution, and the underlying working tree is edited by several lanes at once, so an
entry is evidence of a state at a moment rather than a standing guarantee.

Never treat an inherited red as licence to add one. The gates that are green today, in particular
the action denominator and the import boundary for the frontend, are the ones this campaign is
measured against, and a new failure in them is not excused by the eight above.

Carry the destination-authority entry into the reachability wave's own planning rather than
discovering it there. It is the only inherited failure that sits directly under work this campaign
must perform.
