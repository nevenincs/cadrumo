---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:f2433f85cc797ff68b2a1f8a17b7dd933960a27e422ee167b613eec2f4a3b130'
related:
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-08-03-canonical-storage-management-plan]]'
  - '[[2026-08-03-canonical-storage-management-closure-statement-reference]]'
  - '[[2026-08-03-canonical-storage-management-honesty-review-audit]]'
  - '[[2026-08-04-canonical-storage-management-declared-location-sql-persistence-audit]]'
---

# `canonical-storage-management` audit: `pre-close inherited review`

## Scope

A pre-close pass read as though the campaign had just been inherited, per the
campaign-close honesty rule. Not the final close review — `S78` has open bands
and two findings are in flight.

Everything measured at `19154e664e` and read out of `git show`. Two items the
coordinator flagged as "carrying loosely" were checked rather than taken, and
**both were wrong in the coordinator's favour**.

## Findings

### the-plan-is-113-of-114-and-all-four-flagged-steps-are-closed | none | Every Step the coordinator believed open is checked at HEAD

Checked because the coordinator asked me to rather than take its board state:

**`S62`, `S92`, `S108`, `S114` are all `[x]` at `19154e664e`.** `S108` was
recorded as blocked on `S25`; `S25` landed and `S108` closed behind it. None is
superseded, none is quietly open.

**The plan is 113 checked of 114.** The single open Step is `W03.P16.S78`, the
incidental-literal burndown — which means the campaign's entire remaining planned
work is one Step, and the denominator has held at 114 as intended.

The coordinator's board was stale in the safe direction. Recording it because
the same staleness in the other direction is what a close review exists to catch.

### the-s78-collapse-rule-is-not-verified-and-my-verification-failed | medium | A cheap test of the predictor disagrees with a known result, so the rule must not shape assignments yet

The coordinator's predictor: a literal collapses when the word names something
else in the codebase. Known results — `justificantes` 97 → 0 genuine, `registry`
54 → 2, while `secrets` / `blobs` / `cadrumo.db` were genuine at nearly 100%.

I tried to verify it cheaply, by counting quoted occurrences of each word and how
many sit in a fixture or bundled-data context:

```
justificantes   87 quoted   81 fixture-context     collapse predicted   MATCHES (97 -> 0)
secrets         41 quoted    5 fixture-context     genuine predicted    MATCHES
blobs           44 quoted    1 fixture-context     genuine predicted    MATCHES
registry       258 quoted    7 fixture-context     genuine predicted    CONTRADICTS (54 -> 2)
```

**`registry` breaks it.** My proxy scores it overwhelmingly genuine; the measured
result is 96% collapse. So the proxy is wrong, and a proxy that disagrees with a
known case cannot validate anything.

Why it fails is instructive rather than incidental: `registry` collapses because
of the *modelo registry* and `STORAGE_NAMESPACE_REGISTRY` — referents that are not
fixture paths and often are not quoted string literals at all. And `secrets`
should have collapsed under a naive reading of the rule, since `secrets` is a
stdlib module imported widely; it did not, because `import secrets` never appears
as a quoted path segment. **The predictor is not "does the word name something
else" but "does the word appear as a path segment for a different tree"**, and
those differ.

**The consequence for the campaign is the actionable part.** The rule is
currently shaping band assignments for `live` (65), `runs` (60), `financial`
(47), `iva-wallet` (26), `invoices` (20) and the `llm-*` group (48). It is
unverified, my attempt to verify it failed on a known case, and a wrong
prediction here misallocates whichever lane takes the band. `financial` is the
one to watch: it is a taxonomy segment *and* a `SensitivityClass` member, which
is the same homonym shape that let a liveness claim pass on
`SensitivityClass.AUDIT`.

Not a blocker for closure. A blocker for treating the remaining bands as sized.

### four-buckets-at-head | none | The honest remaining-work list

**Landed and verified** — each read at HEAD, not taken from a commit subject:
the taxonomy and its three resolution entry points; the seven gates including
the directory-agreement and grammar-vocabulary pair; the liveness gate's
namespace qualification, now closed at both instance and class level with a null
re-run; the storage-management service; `dev/write_site_census.py` with its
selector corrections pinned in both directions; 113 of 114 plan Steps; the
`BUCKET_DATABASE_FILE` prefix derivation; the `atexit` cleanup ordering, verified
at delta 0.

**In flight with an owner** — the WAL-vacuity conversion (`conv2`, ~14–18
assertions across ~10 modules); mechanical detection of injected-but-constrained
sites (`rootpath`); the filesystem observation of which declared locations
receive bytes (`honesty`, redesigning after two workloads proved inert and an
accessor-hook design was withdrawn); `S78`'s remaining literal bands.

**Open and unowned** — accessor adoption is unmeasured, and the one number I have
says 5 of 26 production modules import `storage_path` while 21 read settings
fields directly; the declared-location-with-SQL-persistence population is
unbounded after two failed instruments; the `S78` collapse predictor is
unverified per the finding above; whether the two-instrument union covering the
criterion is complete, which no instrument currently answers.

**Deferred with a reason** — `default_rotation_plan`'s justificantes entry, left
to its own reachability question at `rootpath`'s boundary; test-migration and
`W02.P07`/`P08`, out of scope by prior ruling; test hygiene `S84`/`S85`,
explicitly not a closure gate and now complete anyway.

### what-slipped-between-buckets | medium | Three items had no bucket at all until this pass

**Accessor adoption.** Never a Step, never an owner, and it surfaced only because
I overstated a claim about it and had to correct myself. The closure statement
asserts the taxonomy is the single authority; at 5 of 26 that phrasing is doing
more work than the evidence supports. It is not a defect — the provenance gate
governs path *composition*, not which door a consumer opens — but it is an
unmeasured assumption sitting under a closure claim.

**The census tool's own coverage.** `dev/write_site_census.py` is now cited by the
closure statement as the criterion's instrument, and `_trace()` bottoms out at
`self` or a caller parameter for **43 of 98** production sites. That 44%
unresolved floor is a property of the instrument the closure rests on, and it is
recorded in the audit but not beside the citation.

**This document's predecessors.** The closure statement drifted twice in one day
— behind by four findings at one point, and carrying a "class open" statement
after the class was closed. Both were caught by a pass like this one rather than
by any gate. A document that is the campaign's final artefact and has no
freshness check is a standing risk, not a one-off.

## Recommendations

Treat the `S78` collapse predictor as unverified and say so in whatever assigns
the remaining bands. If it is worth verifying, the test is per-literal
classification of a sample against the prediction, stated in advance — and
`financial` is the sharpest case because of the `SensitivityClass` homonym.

Give accessor adoption an owner or an explicit deferral. Either is fine; being in
neither bucket is not.

Put the census tool's 44% unresolved floor beside its citation in the closure
statement, not only in the audit. A reader who follows the citation should meet
the limit at the same time as the number.

Add a freshness line to the closure statement naming the commit it was last
reconciled at, so the next reader can tell in one glance whether it has drifted
again rather than discovering it four findings later.

## Verdict

**The campaign is in a closable state on its planned work and not on its open
questions, and the distinction is clean rather than blurred.**

113 of 114 Steps, with the remainder a single burndown Step whose scope is
disputed rather than unknown. Every artefact I checked at HEAD matched its
claim, and both items the coordinator flagged as loosely held turned out better
than believed — four Steps closed rather than open, and a stale board rather than
hidden work.

What is not closable is the set of open questions, and they are honestly
recorded: an unbounded dormancy population after two failed instruments, an
unverified collapse predictor now shaping assignments, unmeasured accessor
adoption, and a two-instrument union whose completeness nothing establishes.
None of these blocks the plan; all of them would be misrepresented by a closure
statement that did not name them.

**The one thing I would not close over** is `5f`, the WAL vacuity. It is owned
and in flight, but until it lands the product's encryption-at-rest claim is
asserted by roughly fifteen tests that would pass against a build with
encryption switched off. That is not an open question — it is a defect with a
fix in progress, and closure should follow it rather than precede it.
