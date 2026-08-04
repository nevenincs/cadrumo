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

### the-s78-collapse-rule-is-unverified-and-my-proxy-could-not-test-it | medium | Corrected on second read: the proxy did not disagree, it was structurally unable to agree

**Correction, recorded in place.** This finding first read *"a cheap test of the
predictor disagrees with a known result"* and described `registry` as
*contradicting* the rule. **Both overstate.** The second reader applied the
standard I had asked it to apply to me: could the measurement have produced the
other answer?

It could not. My proxy scores a literal by counting quoted occurrences in a
fixture or bundled-data context. `registry` collapses through the *modelo
registry* tree and `STORAGE_NAMESPACE_REGISTRY` — referents that are frequently
not quoted string literals at all, as this finding's own body says. So there is
no reading under which the proxy scores `registry` as collapsing. **A test that
cannot agree has not disagreed.**

The distinction changes what happens next, which is why it is worth the
correction rather than a footnote: *contradicted* invites the next reader to
discard a rule that has never been tested, while *unverified* leaves it standing
and untested, which is its actual state. The recommendation is unchanged — it
must not size the bands — and the diagnosis of **why** the proxy fails survives
intact and is the part worth keeping.

The original finding follows, because a refutation that turns out to be
unearned is exactly the shape this review exists to catch, and deleting it would
remove the evidence.

### the-original-refutation-claim | superseded | A cheap test of the predictor disagrees with a known result

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

### s114-is-complete-as-scoped-and-the-residual-is-a-different-duplication | none | Checked, recorded, and narrower than a reader would assume

Checked because the coordinator saw `S114` as both pending and completed and did
not know which was true. **Both, for two different reasons, and neither is a
defect.**

The board carried two tasks for one Step — a duplicate — and the checkbox is
right: `S114` is `[x]` at HEAD with an exec record whose claim is precise.

**My first read of the code said partial and was wrong.** Fourteen grammars are
now f-string interpolated and fifteen remain plain literals, which looks like
half-done work. The exec record explains it: the Step's scope was entries that
spelled a segment **twice within the same module** — once in `segment=`, once
retyped inside `grammar=`. The fifteen remaining have no `segment=` field at all,
so there was no second spelling to collapse. Complete as scoped.

**The residual is real and is a different duplication.** Those fifteen — the
blob, run-trace, `llm-usage`, `llm-run-telemetry` and `tokens` fan-out shapes —
still hand-type a directory segment that a `StorageCategory` declares. That
duplication is **across modules** (taxonomy against definitions), not within one,
and the directory-agreement gate **pins it rather than eliminating it**. It is
the finding from the original self-duplication review, still open, and `S114`
never covered it.

Recording the distinction because "checked but not done" and "done, but scoped
narrower than a reader assumes" look identical on a board and need different
responses. This is the second, and the exec record is what made it decidable —
an argument for the exec-record requirement that is easy to lose.

### the-criterion-ruling-settles-the-adoption-question | none | Established by two named gates rather than by judgement

The accessor-versus-field question raised by the 5-against-21 measurement is
**settled and no longer a matter of judgement**, on two gates green at HEAD:

`test_storage_binding_gate.py` proves every `Path`-typed `Settings` field is a
taxonomy member, a declared escape, or the storage root — **total and disjoint** —
and its discovery is anchored to `Settings.model_fields` deliberately independent
of the taxonomy, so the two sides cannot move together and pass vacuously.
`test_storage_default_parity.py` pins each field's placeholder default to the
taxonomy's subpath.

So a field read is a **gate-guaranteed member with a parity-pinned default**, not
a second authority:

```
storage_path(StorageCategory.X)   ENROLLED
settings.cadrumo_x_dir            ENROLLED   (member by gate, default by parity)
storage_root / "llm-cache"        NOT enrolled -- this is what S78 burns down
```

**Accessor versus field is style, not enrollment.** The adoption gap is hygiene
and stays out of the criterion; if the closure statement's language overstates
adoption, the language narrows rather than 21 modules migrating for zero
enrollment gain.

Worth noting what the ruling does *not* remove: the parity gate makes the
duplicate safe, it does not make it one declaration.

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

**Open and unowned** — accessor adoption, measured below rather than as a ratio;
the declared-location-with-SQL-persistence population, unbounded after two failed
instruments; the `S78` collapse predictor, unverified per the finding above;
whether the two-instrument union covering the criterion is complete, which no
instrument currently answers.

**Deferred with a reason** — the dynamic observation of which declared locations
receive bytes, **closed rather than in flight**: three instruments, three
structural failures, and the conclusion that a category resolved once at import
into a constant is a static fact, so it is handed to the static scanner;
`default_rotation_plan`'s justificantes entry, left to its own reachability
question at `rootpath`'s boundary; test-migration and `W02.P07`/`P08`, out of
scope by prior ruling; test hygiene `S84`/`S85`, explicitly not a closure gate
and complete anyway.

### my-adoption-figure-was-wrong-twice-and-the-denominator-was-constructed | medium | Corrected: 8 accessor modules, 24 field modules, 1 in both, union 31

**"5 of 26" should not have been published, and both halves were wrong.**

The **5** came from a grep pattern of mine — `import storage_path\|storage_path,`
— that misses `from .. import StorageCategory, storage_path`, a name at
end-of-line with no trailing comma. That is the substring-and-pattern trap I had
flagged in two other lanes' measurements the same day, committed in my own. The
second reader found it by checking whether the two sets overlapped.

The **26** was worse in kind: it was `5 + 21`, the sum of two samples presented
as a population. A constructed denominator reads as a measured one, which is the
literal-corpus lesson in a different costume.

Re-measured at `5da2b328f9` with a call-form predicate:

```
modules calling storage_path(          8
modules reading a bound path field    24
in both                                1    core/observability/_store.py
union                                 31
```

The overlap module and its identity are exactly what the second reader predicted.

**Report it as three numbers, never as a ratio.** "8 modules call the accessor,
24 read a bound field, 1 does both" lets a reader form their own view; "8 of 31"
implies a population nobody has measured — the real denominator is however many
production modules resolve a storage location at all, which remains unmeasured.

The substantive conclusion is untouched: adoption is hygiene, not correctness,
because the enrollment ruling makes a field read taxonomy-governed either way.

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
