---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:d1e02eb288d401f270db2e9c90a75c9eedeb0926408d4c6b8646c40344a8d42c'
related:
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-08-03-canonical-storage-management-closure-statement-reference]]'
  - '[[2026-08-03-canonical-storage-management-closure-criterion-census-audit]]'
  - '[[2026-08-03-canonical-storage-management-dormancy-burndown-audit]]'
---

# `canonical-storage-management` audit: `declared location, SQL persistence`

## Scope

Three members now describe a filesystem location whose records actually live in
the encrypted SQL `secure_objects` table. Asked whether that is a pattern, how
many more there might be, and what it implies for the taxonomy.

Pinned to `53d2c9b73425146faadf1e482e9b1895f826c1fe`, read through `git show`.
Grounded first by `vaultspec-rag` semantic probe, then confirmed by reading.

## Findings

### it-is-a-pattern-and-the-population-is-unmeasured | medium | Three instances share one mechanism, but no instrument we have can bound how many more exist

**A pattern, on the evidence.** The three share a single mechanism rather than a
resemblance: a location declared when persistence was filesystem-shaped, a
migration of that data into `secure_objects`, and a declaration left standing
because nothing forces a declaration to justify itself against where bytes
actually land. Three found *incidentally*, while looking for other things, is
weak evidence of frequency and strong evidence of invisibility — nobody was
looking, and they surfaced anyway.

**The population is unknown, and I could not bound it.** That is the substantive
result of this audit and it is a negative one.

### the-instrument-fails-its-own-positive-control | high | A probe over all 58 members misses the confirmed instance, so its silence about the other 57 means nothing

I built a probe over the pinned taxonomy: for each `StorageCategory` member, do
any of its referencing production modules contain a filesystem write primitive?
It reported **17 of 58 members with none**.

That number should not be used, for two independent reasons.

**It is dominated by a category that is designed this way.** Most of the 17 are
nested leaves — the keystore sidecars, the `audit/live/*` chain, the submissions
nested segments, the cache file leaves, `ATTACHMENTS_MANIFESTS`. Those members
exist to govern a *name*; their consumers resolve through the parent's settings
field and cross-reference only the bare filename off the member. Having no direct
writer is their declared design, recorded in the taxonomy's own comments. They
are not dormant.

**And decisively, the probe does not flag the known positive.**
`StorageCategory.JUSTIFICANTES` — the confirmed third instance — is absent from
its output, because the member's declared consumer `_rotation.py` does contain
write primitives. They simply do not write *there*. **An instrument that misses
the one case known to be true cannot bound the cases not yet known.** The 17 is
not a floor, not a ceiling, and not evidence.

Recording the failed probe rather than discarding it, because the reason it fails
is the finding: every cheap instrument available asks a *proxy* question.

### why-static-analysis-cannot-answer-it | high | Reference and write are both proxies, and this pattern defeats each one separately

Three questions, easily confused, and the pattern slips between them:

**"Does a module reference this member?"** — the liveness gate. Passes for
`JUSTIFICANTES`: `_rotation.py` genuinely references the field.

**"Does a referencing module write to disk?"** — my probe. Also passes: that
module writes, just elsewhere.

**"Do bytes ever land at this path?"** — the question that actually matters, and
the only one that separates a live location from a migrated one. Neither static
instrument asks it, because answering it requires knowing the *destination* of a
write, which is precisely what the pass-through analysis in the closure criterion
established is unknowable statically for roughly half of all write sites.

So this is not a gap to close by tightening a selector. It is the same
pass-through wall from a different side: there the caller-supplied path had no
enrollment answer, here the module-level reference has no destination answer.

**What would settle it** is a filesystem question, not a source question: exercise
each feature and observe whether the declared directory receives bytes. A
before/after snapshot sees the result however the write happened, which is the
shape this project already found necessary for absence claims after a
primitive-wrapping census reported a false zero.

### the-conv2-overlap-prediction | medium | The namespace fix and the dormancy set are probably different sets, and confirming that is cheap

Asked to coordinate rather than duplicate, and the coordination is worth stating
as a prediction the re-run will confirm or refute.

The liveness gate's namespace weakness is that a claim can be satisfied by an
attribute of an unrelated type sharing the member's name. Fixing it makes the
*reference* question accurate. It does not change which question is asked.

**So a member whose reference is genuine but whose writes go to SQL passes the
old gate and the fixed gate alike.** `JUSTIFICANTES` is the worked example:
`_rotation.py` is a true reference by any definition, collision or not. The
newly-failing set should therefore be members whose *only* evidence was a
collision, and the dormancy set members whose evidence is real but whose bytes go
elsewhere. **Different populations, possibly overlapping, definitely not the
same.**

If the re-run's failing set turns out to *be* the dormancy set, that refutes this
and is a much more interesting result — it would mean collisions and migrations
co-occur, which nothing predicts.

### severity-is-reachability-not-declaration | medium | A bare declaration is dead weight; the rotation entry is the part that could bite

Stating reachability as the variable rather than assigning one severity to the
class.

**A declared location nothing writes to is not a defect.** It is dead weight: it
costs a reader a wrong mental model and costs an operator a row in
`config storage list` for a directory that will always be empty. Both real, both
cheap.

**It becomes a defect when something acts on it.** Two reachable paths:
a reader that resolves the location and gets an answer that is structurally valid
and semantically empty; or a rotation/cleanup plan that enumerates it as though
it held records.

**For the third instance the second path is live.** At the pinned commit
`cadrumo_justificantes_dir` has exactly **three** production references: the
taxonomy declaration, `core/config.py`, and `adapters/persistence/storage/_rotation.py`.
The last is a `RotationPlanEntry` in `default_rotation_plan` describing a
`.envelope.json` file shape that nothing writes. So the only thing reaching this
location is a plan to act on records that are not there.

**Not reopened, deliberately.** `rootpath` stopped at that boundary and the stop
was correct: the fix it landed was on the blob-store side, and reversing this
entry is a different function with its own reachability question. Recorded here
as the reachability variable, not as work.

## Recommendations

Treat the count as open rather than estimating it. Three confirmed, population
unmeasured, and the failed probe recorded above is the reason a number would be
invented rather than measured.

Settle it with a filesystem observation if it is worth settling: exercise each
feature owning a declared location and check whether the directory receives
bytes. That is a bounded exercise over 27 members with settings fields, and it
answers the question the static instruments cannot.

Confirm or refute the overlap prediction against `conv2`'s newly-failing set. It
costs one comparison and it determines whether one fix addresses both classes or
neither.

Consider whether the taxonomy should carry a declared axis for *persistence
substrate* — filesystem versus secure-object — so a migration has somewhere to be
recorded. Three members currently describe a substrate they no longer use, and
nothing in the declaration can express that. This is an ADR-shaped question about
whether the taxonomy models storage location or storage medium, and it is named
here rather than decided.

## Verdict

**Yes, a pattern — and no, I cannot tell you how many.**

The mechanism is real and shared across three instances, and the fact that all
three surfaced incidentally suggests the class is invisible to routine work
rather than rare. But the instrument I built to size it fails its own positive
control, and the two instruments the campaign already owns each answer a proxy
question this pattern is specifically shaped to slip past. Reporting 17 would
have been worse than reporting nothing.

**It belongs in the closure statement, and as an open question rather than a
count.** The reason is that it bears directly on the criterion: a declared
location nothing writes to satisfies "all file-producing sites are enrolled"
*trivially and vacuously* — there is no site to enrol. A criterion that a dead
declaration passes for free is one more place where silence reads as coverage,
which is the failure the whole campaign exists to surface. One paragraph, the
three instances, the reachability variable, and the fact that the population is
unmeasured.
