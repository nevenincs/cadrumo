---
tags:
  - '#reference'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:99110edd51d8ab630da3f7d2484db7b1f27f7992b1428e14a30af50e7785d382'
related: []
---

# `canonical-storage-management` reference: `canonical storage management closure statement skeleton`

## Summary

Drafted as a skeleton against known-shaped evidence while measurement was still
in flight, so the statement could be assembled rather than composed under time
pressure. Every section states what the evidence will be, which artefact carries
it, and — the part a closure document usually omits — what would have to be true
for the answer to that section to be "no". A skeleton with a shape only for "yes"
will find one; this was written to be equally capable of concluding either way.

**The criterion element is now resolved, and it did not resolve to a number.**
The operator's criterion — *"if we can satisfy that all file producing sites are
enrolled we're done"* — turns out not to be decidable over the set it names,
because nearly half of all write sites are handed their path by a caller and so
have no enrollment answer of their own. Restated over path-*choosing* sites it is
decidable, and it holds. Element 5 carries the measurement, element 5a the two
instruments and their blind spots, and the verdict states the one sentence that
can be defended in place of the one that cannot.

**Read the verdict as governing the criterion element only.** The remaining
elements keep their own statuses, and the conjunction rule below still governs
the whole.

## How to use this document when the evidence lands

For each element below, replace `STATUS: pending` with `STATUS: satisfied`
or `STATUS: not satisfied`, cite the artefact that proves it (a commit, a
test file, an exec record — never a chat message or a scratchpad file alone),
and answer the "what would make this no" question explicitly rather than
silently dropping it once the answer turns out to be "yes". The final verdict
is the conjunction of every element's status — one "not satisfied" makes the
whole statement "no", regardless of how many other elements are clean.

## The prominent blocker — read this section first

**STATUS: closed.** This section previously blocked the whole document; it
no longer does, and is kept first and this detailed so a reader can verify
the closure rather than take it on trust.

Both of this campaign's own gates — `test_storage_liveness_gate.py::test_every_consumer_claim_is_backed_by_a_real_reference`
and `test_settings_lifecycle_gate.py::test_no_production_module_names_an_operator_data_location_by_literal`
— traced to one unlanded change: five `var/cadrumo/...` literals in
`_app_live.py`/`_overview_evidence.py`. **The change landed** ("fix(cli):
enrol the live-read and filed-declaration roots in the taxonomy") —
**adopted rather than authored**: found complete and unattributed in the
working tree, predating this session, landed on operator directive rather
than committed unilaterally by the coordinator who had flagged it as stuck.

**Provenance**: measured by the plan/vault agent directly, and measured
the way this document's own carry-forward section prescribes after
catching itself failing to. `PINNED=$(git rev-parse HEAD)` resolved to
`c16bb9a0ae`; the working tree's `_storage_taxonomy.py` carries substantial
uncommitted peer WIP for the still-open Family 1/2 declarations, so an
in-place run would have risked exactly the dirty-tree contamination
mechanism 1 describes. `git archive "$PINNED"` extracted to a clean
scratch directory instead; both gates run from that archive: **2 passed**.

**What would have made this "no", preserved for the record**: the fix
never lands, or lands but a fresh serial single-SHA gate run — SHA
resolved into a variable before archiving — still shows either test red.
Neither happened. **No other evidence in this document could have
outweighed a "no" here** — that asymmetry is why this section stays first
even now that it is closed, rather than being folded into the numbered
list below.

## Criterion elements

Each element states the plan Step(s) that carry it, the artefact that will
prove it, and the falsifying condition.

### 1. The cheapest refutations — `S51`, `S52`, `S53`, `S24`

**STATUS: partial.** `S24` closed ("fix(core): enroll active-profile
pointer path through the storage taxonomy") — `pointer_path()` now calls
`storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).relative_path()`;
no exception was needed, since the taxonomy module has no runtime import
path back to `config.py` and the pre-existing deferred, submodule-qualified
import was sufficient on its own. **This is the third instance in this
campaign where a checked Step did not match landed code** (`S42`, `S54`
unaccountable-checkbox flips that turned out genuinely done; `S24` checked,
found genuinely not done, unchecked, now genuinely done) — the only one of
the three where the checkbox itself was wrong rather than merely
unaccountable. `S51`, `S52`, `S53` remain open — their cited file:lines
still read `load_settings()` directly, not re-verified again since the last
pass.

**Provenance**: `S24` verified directly against committed HEAD
(`git show HEAD:src/cadrumo/core/_bucket_pointer_io.py`) by the plan/vault
agent. `S51`–`S53` still carry the earlier caveat: measured via `git show
HEAD:<path>` reads with no SHA captured — re-verify before citing as
settled.

**Evidence**: each remaining site re-pointed onto `storage_path`/the
accessor, verified by reading the changed file at a pinned SHA, not by
trusting the Step checkbox.

**What would make this "no"**: any of `S51`–`S53` still reads the location
directly at closure time, or a Step is checked without the corresponding
code change present at the cited SHA.

### 2. NESTED-UNGOVERNED families — `S86`–`S92`, `S107`

**STATUS: partial — named explicitly rather than left as a fraction.** Four
items closed, three of the four via the same distinction (already declared
under a different name), the fourth (`S89`) via real declaration work.

- **`S86`, `S87`, `S88`** — closed via the `StoragePathDefinition` grammar
  mechanism, a discovery about the record, not progress against the work.
- **`S89` — the secret store's five file leaves — closed for real.**
  ("feat(storage): declare the secret store's five file leaves and gate
  directory-grammar drift.") Five new `FIXED`, no-`settings_field`
  taxonomy members, each cross-referencing only the bare filename its
  producer already resolves via the settings field it reads — composing
  root + subpath through `storage_path()` was rejected deliberately, since
  `SECRETS` is operator-overridable and that composition would silently
  disagree with a real override. A new directory-grammar agreement gate
  landed alongside, with two positive controls, and it found a genuine
  separate gap named as `S108` below rather than fixed inline.

**Still open, named individually:**

- **`S90`** — the `audit`/`live` intermediate segment plus `live/iva-wallet`,
  `live/iva-remote-state`, `filed-history`, `wallet`. **Uncommitted peer WIP
  exists for this in the working tree** (`_storage_taxonomy.py` carries
  `AUDIT_LIVE*` members not yet committed as of this reconciliation) — real
  progress, but not yet landed; do not mark closed on the strength of the
  working tree.
- **`S91`** — `submissions/amendments`, `submissions/amendment-results`,
  `financial/attachments/manifests`. **Same uncommitted-WIP caveat as
  `S90`.**
- **`S107`** — five filename-template patterns. Mechanism confirmed
  applicable (no ruling needed); grammars not yet declared.

**Provenance**: `S86`–`S89` verified by the plan/vault agent directly
against committed HEAD `c16bb9a0ae`. The `S90`/`S91` uncommitted-WIP
observation is from a `git status --short` read at the same session,
timestamp not separately captured — re-check status before citing whether
it has since landed.

**Evidence**: each remaining family declared with its own conformance test,
or explicitly re-classified as an OPERATOR-DIRECTED escape with a stated
reason.

**What would make this "no"**: any of the three remaining items undeclared
at closure time, or declared with a grammar/member that a real-write
conformance test doesn't actually exercise.

### 3. Settings-defaults contradicting the taxonomy — `S105`

**STATUS: pending.** Five settings-field defaults (`cadrumo_registry_parity_store_dir`
plus four `var/`-prefixed fields) disagree with their declared taxonomy
subpath. Dead at runtime (the derived-output validator overrides from the
taxonomy), but a second, drifted declaration nothing compares.

**Provenance**: measured by the honesty reviewer, in-process comparison of
every bound field's default against its member's `relative_path()` (20
agree, 2 opt-in with no default, 5 disagree). **Not independently
re-verified by the plan/vault agent** — taken from the audit document as
reported, not re-read against code directly. Re-verify before treating as
settled.

**Evidence**: the five defaults corrected, and — the part that makes this
not recur — a gate asserting every bound field's default equals its
member's `relative_path()`, per the audit's own recommendation.

**What would make this "no"**: the five values corrected but no comparison
gate added, since that leaves the exact defect class (a dead but drifted
second declaration) able to recur silently on the next new field.

### 4. The containment-proof blind spot — `S106`

**STATUS: pending.** `reclaim`'s containment proof quantifies over declared
taxonomy members, so it cannot see undeclared nesting beneath an accepted
category — safe today only because every known undeclared site sits under
an `unbounded_by_design` parent, not because the proof asserts anything
about it.

**Provenance**: measured by the honesty reviewer, reading the proof's
implementation and its own docstring. **Not independently re-verified by
the plan/vault agent.**

**Evidence**: either the proof extended to catch undeclared nesting (hard,
since by definition it doesn't know what it doesn't know), or an explicit
statement in the ADR that this is an accepted residual risk with the reason
stated, so a future member declared `RETENTION` with undeclared nesting
beneath it is a decision someone took rather than a gap nobody noticed.

**What would make this "no"**: the gap is neither closed nor acknowledged
— i.e. this document ships silent on it, which is the exact failure mode
the closure-criterion reference exists to prevent.

### 5. The criterion is not decidable as worded, and the write-site census is why

**STATUS: satisfied, with the criterion restated.** This element asked for a
manual review of the ~99 write sites. The review was performed by census
rather than by hand, and it returned something stronger than a classification:
**the criterion cannot be evaluated over the set it names.**

**Provenance**: `dev/write_site_census.py`, landed with its test at commit
`30f2493ee1`, quantifying over write primitives in the AST rather than over the
taxonomy — the direction that matters, since a census iterating declared
members cannot see an *un*enrolled site. Recomputable at any revision by
`python -m dev.write_site_census <revision>`; the figure is deliberately not
restated here as a bare number, because a count in prose has no maintainer and
this corpus has already lost two to that.

**Evidence**: classified by where the written path comes from, roughly
**44 of the sites are pass-through** — the path arrives as a caller argument or
as a `self` attribute set by a constructor. A primitive doing
`path.parent.mkdir()` on a path it was handed **has no enrollment answer of its
own**; its answer is "wherever the caller said". Asking whether such a site is
enrolled is not a question with a truth value, and nearly half the domain is in
that state. This element's earlier estimate of "roughly fifteen" pass-through
primitives was low by a factor of three, and the difference changes the
conclusion rather than refining it: at fifteen it is an edge case, at
forty-four it is the dominant shape.

**The criterion becomes well-formed over path-*choosing* sites** — the places
that decide a location rather than the places that write to one. That set is
strictly smaller and, unlike the write set, decidable: choosing a path means
composing it from a root or a declared field, which is a syntactic act.

**What would make this "no"**: a closure statement that quotes a site count as
if it settled the question, without recording that nearly half the sites have
no answer to give.

### 5a. The two-instrument union, with each blind spot named beside it

**STATUS: satisfied.** Restated over path-choosing sites, the criterion is
carried by **two instruments, neither sufficient alone**, and a reader who finds
only one will reasonably conclude the coverage is complete.

**Instrument one — the provenance gate.** Walks every packaged module,
production and test, and requires any site composing a path from the storage
root to be a declared producer. Green, with `PENDING_ENROLLMENT` reduced to the
empty tuple in a table declared to only ever shrink. **Blind spot:** it keys on
the *root*. A site joining a literal onto a *category* field never touches the
root symbol and is invisible to it.

**Instrument two — the taint-based family census.** Covers exactly that
category-composed class, and its four families are declared. **Blind spot:**
incomplete by construction for the four classes it names — cross-module
composition, library-named files, container-mediated flow, and fully dynamic
expressions.

**Blind to both:** writes through a retained handle, where one syntactic site
performs unbounded real writes, and duck-typed method names that no static pass
can separate from their filesystem namesakes without type inference.

**What would make this "no"**: recording the union as though it were a proof.
It is two partial covers whose overlap is unmeasured; that is materially better
than either alone and materially weaker than completeness.

### 6. Runtime census cross-check

**STATUS: pending.** The audit's own stated method for the tightest
defensible bound: intersect the ~99 static sites against the frames the
instrumented runtime census (`S103`) actually observed, to make the
residual ("sites that both compose cross-module and are never exercised")
a named, finite list rather than an open question.

**Provenance**: not yet computed. When it lands, cite the two input
artefacts by their pinned measurement (the static site list's SHA, the
runtime census's suite-run identity) rather than by name alone — an
intersection of two unpinned measurements inherits both their staleness
risks.

**Evidence**: the intersection computed and persisted, with the residual
list named explicitly — even if the residual is non-empty, naming it is
what this element requires, not eliminating it.

**What would make this "no"**: the intersection is never computed, so the
residual stays an unmeasured "probably fine" rather than a bounded list.

### 7. Test hygiene — `S84`, `S85` — explicitly not a closure gate

**STATUS: N/A to the verdict, tracked separately.** Per the operator's
second re-scope, test cleanup is a different standard (nothing a test
creates should survive the test) with its own empirical evidence
(snapshot-diff before/after a suite run), and does not gate this criterion
even if its own findings (e.g. the `cadrumo-settings-*` leak already found)
remain open at closure time. **State this plainly in the final document
rather than silently omitting test hygiene** — an omission reads as an
oversight, a stated exclusion reads as a decision.

**Provenance**: no measurement performed yet; `S84`'s snapshot-diff census
is authored but not run. Not required for the verdict, so its absence does
not block closure — but if it runs before closure, cite it the same way as
the other elements (who, method, pinned-or-not) rather than as prose.

### 8. Test-migration and W02.P07/P08 — explicitly out of scope

**STATUS: N/A to the verdict.** `S76`–`S78` (bulk test-literal migration)
and `S93`–`S100` (effective-storage-root and optional-root-resolver
convergence) are real drift reduction, re-scoped out of the closure path
by the operator's own criterion. State their open count in the final
document so a reader doesn't mistake plan-completion-percentage for
closure-percentage, but do not let their open count affect the verdict.

**Provenance**: plan Step counts (`S76`–`S78` open; `S93`–`S100` open),
read directly from `vaultspec-core status` at time of writing — the plan
tool's own state, not an independent measurement, and it moves as Steps
land. Re-read at closure time rather than citing this document's number.

### 9. Two findings from this wave, not yet fixed — `S108`, `S109`

**STATUS: pending, both.** Real, verified, newly discovered while
reconciling this wave rather than commissioned in advance.

**`S108`** — the new directory-grammar agreement gate (landed with `S89`)
found `application/_config_reset_repository.py` carrying its own duplicate
`CONFIG_RESET_JOURNAL_DIRNAME = "reset-operations"` constant, joined onto
the raw storage root, bypassing `storage_path()` entirely — even though
`_storage_path_definitions.py` already declares this exact shape
(`config_reset_journal`). Named as an exemption in the gate rather than
fixed or laundered; this Step tracks closing it. **Provenance**: verified
directly by the plan/vault agent against committed HEAD `c16bb9a0ae`
(`git show HEAD:src/cadrumo/application/_config_reset_repository.py`).

**`S109`** — `src/cadrumo/tests/test_compatibility_lifecycle_gate.py::test_the_enrollment_predicate_names_every_uncovered_durable_format`
is red at HEAD, campaign-caused: this campaign's own persisted-format
declarations added `bucket_database_file` and `secret_index`, and the
gate's hand-written expected tuples were never updated to include them.
Routed (open, not yet fixed). Consider deriving the expectation from the
declared formats rather than restating it by hand — a hardcoded census of
uncovered formats is the gate shape this project forbids elsewhere.
**Provenance**: run directly by the plan/vault agent, working tree (not a
clean archive — this test file itself has no uncommitted changes, but the
run was not pinned): `pytest src/cadrumo/tests/test_compatibility_lifecycle_gate.py::test_the_enrollment_predicate_names_every_uncovered_durable_format`,
**3 failed** (all three parametrised cases), confirming the same cause the
coordinator named.

**What would make either "no" if closure were declared today**: both are
open, unambiguously — `S109` in particular is a currently-red test, the
same class of evidence that gated the prominent blocker above, just in a
different gate.

## Carried forward unchanged — three things a reader most needs

**Step state is a claim, not evidence.** Three times in this campaign a
checked plan Step has not corresponded to landed code (`S42`, `S54`, `S24`
— the first two unaccountable-checkbox flips later verified genuinely
done, the third checked and found genuinely not done). Every element above
must be verified against the cited artefact directly; a checked Step is a
starting point for verification, never a substitute for it.

**The five measurement-mechanism failures this campaign catalogued, all of
which survived their own verification because something real was measured
and the wrong name attached to it:**

1. A gate run in a dirty working tree, reported as a HEAD fact — twice.
2. A peer's uncommitted-lane observation relayed as a fact about HEAD,
   unchecked.
3. `git archive HEAD` run, then `git log -1` run *afterwards* to label it
   — a commit landed in between, so the parent was measured and the
   child's SHA reported.
4. A 62-minute full-tree run against a tree receiving commits throughout,
   measuring no single state — 2 of 21 reported failures were already
   fixed by the time the run finished.
5. The inverse of the first four: the object was right, but the
   instrument's selector was broader than the concept it was named for —
   a "production filesystem-mutating call sites" census matched every
   `.replace(...)` attribute call, so `str.replace` scored as `Path.replace`;
   267 reported, 166 false positives, ~99 real.

**A sixth instance, and it is this document, not a source it cites.** The
first draft of the prominent-blocker section above stated "3 unbacked
consumer claims became 13" and read the campaign's enforcement as
regressing — mechanism 3, reproduced inside the very document warning
against it: the measurement behind that sentence came from `git archive
HEAD` run, then `git log -1` run afterwards to label it, with a commit
landing in the gap. Found by re-reading the source the sentence cited
rather than trusting an earlier citation of it, and corrected to the true
arc, 3 → 13 → 3, in the section above. **The catch is better evidence that
this discipline works than the list of five ever could be** — a document
that states a rule and then is shown violating and self-correcting under
that same rule demonstrates the rule bites its own authors, not just the
measurements it was written to critique. A reader trusting these six
mechanisms should expect them to catch the next person too, including
whoever finalises this statement.

The discipline this closure statement must follow, stated once so every
section above can rely on it without restating it: **resolve to an
immutable object first, measure that object, report that object — never
report the name.** `PINNED=$(git rev-parse HEAD)`, then measure against
`$PINNED`, then report `$PINNED`. When two measurements disagree, the
difference is almost always in the setup, not in which one is wrong.

**The named limits — state these explicitly in the final document even if
they remain open, because a closure statement silent on a known limit
reads as though the limit was never found:**

- `cadrumo_database_url` is `str`-typed and invisible to the `Path`-typed
  binding machinery — confirmed real, not yet resolved.
- The runtime write census is blind to directory creation (a companion
  `dir_census.py` pass is written but not yet run) and, by construction,
  to any code path the instrumented suite run never exercises.
- The POSIX root-permission-drift assertion and the mode-bit test
  (`S81`) have never executed on a real POSIX host — guarded-inline makes
  them non-vacuous where they run, which is not the same as verified.
- A named transport-primitive class whose enrollment question relocates to
  its call sites rather than resolving at the primitive itself. **Source,
  per the coordinator: the manual read of the ~99 sites (element 5), not
  the coordinator's own measurement** — roughly fifteen are pass-through
  primitives doing `path.parent.mkdir(...)` on a path they were handed, so
  their static answer is definitionally "wherever the caller said," pushing
  the enrollment question to each call site rather than the primitive.
  Carried forward as stated; whoever finalises this document
  should re-verify and cite the specific primitive and call sites before
  the statement ships, since this skeleton does not yet have independent
  verification of that claim.

**What the self-duplication audit (`021c3bae46`) found clean, recorded because
it is load-bearing for closure and a reader should not have to take it on
faith:** layering verified with no upward `core → adapters` import; the
storage-management service composes existing primitives rather than
re-implementing them; no two of the seven gates detect the same condition
(read against each other individually); nothing the campaign added is an
unconsumed public symbol; all three deliberate separations this campaign
decided against merging (the independent-oracle test, the five no-`settings_field`
secret-store members, the SQL secure-object namespace split) are re-verified
on evidence, not merely re-asserted; and 129 tests across eleven gate
modules pass. Four new findings from the same audit are tracked as `S111`–`S114`
and as the `R16` correction, above and in the closure-criterion reference's
fragile-spots section — the clean result does not cover them, and citing the
clean parts should not be read as covering the open ones.

## This document was itself untracked until hours before closure

Recorded as a finding rather than quietly fixed, because it is the exact class
of gap the campaign exists to surface and a reader who sees only the polished
version would never know.

**This file had never been committed.** `git log --all` on its path returned
nothing; it existed only in one working tree. It was not alone: **104 exec
records existed on disk and 68 were tracked**, so 36 — a third of the evidence
every Step's completion rests on — had no git object behind them. Found by this
campaign's own corpus audit, hours before closure was to be declared, and
committed at `7d09fb29f0` after each was checked complete and confirmed to be a
new-file add carrying no peer working-tree content.

Three things make it worth keeping rather than erasing:

**The campaign nearly closed a third short of its own evidence.** A closure
statement citing exec records that a fresh clone does not contain cites nothing
durable, and `plan-closure-requires-exec-records` makes those records the whole
basis of a Step's completion.

**Every corpus figure quoted before `7d09fb29f0` measured 68 records while 104
existed.** Not wrong about what it examined — wrong about what it was examining.
That is the untracked-file trap in its most expensive form, and it is the same
shape as measuring a working tree and calling it HEAD, inverted: there the name
resolved to the wrong object, here the object was a third of the corpus.

**Untracked is worse than uncommitted.** A modified tracked file has a git
object behind it and is recoverable. An untracked file has none — it is
invisible to `git grep`, to every HEAD-anchored audit, and to recovery.

## Verdict

**The criterion as worded is not decidable. Restated over path-choosing sites it
is decidable, and it holds at the pinned revision.**

What can be defended, and what should be written rather than a percentage:

> No unenrolled path-choosing site is detectable by either instrument at the
> pinned revision, and the residual is bounded by three named classes rather
> than by an assertion.

What must **not** be written is *"all file-producing sites are enrolled"*. Nearly
half of them have no enrollment answer to give, so the sentence is not true, not
false, and not checkable — and a campaign that exists to stop a silence being
read as coverage must not close by doing exactly that.

**The plan's completion percentage neither establishes nor refutes this.** The
plan counts Steps; Steps are a proxy. A reader arriving at this document will
reach for that percentage first precisely because it is the one number that looks
like an answer, which is why it is named here and set aside.

**Remaining elements** keep their own statuses above. This verdict resolves the
criterion element only; the conjunction rule stated at the top of this document
still governs the whole, and one "not satisfied" elsewhere still makes the
overall statement "no".
