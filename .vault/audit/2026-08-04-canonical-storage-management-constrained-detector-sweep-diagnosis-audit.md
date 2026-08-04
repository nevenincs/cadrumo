---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:c31ae5f5d8d4f3ede0cbe5a8168c63862bfc0106b66d909ae2c42bf7a55426a4'
related:
  - "[[2026-08-04-canonical-storage-management-collapse-predictor-verification-audit]]"
---

# `canonical-storage-management` audit: `constrained detector sweep diagnosis`

## Scope

The `--scope tests` "injected-but-constrained" detector (`WriteSite.constrained`,
`dev/write_site_census.py`) was built to catch a literal that reads as free
(`temporary`/`pass_through`) but secretly agrees with a value a sibling fixture or
a spawned process independently derives from the real taxonomy accessor. Before
trusting it as a triage instrument, it was run against the full test tree and
checked against three oracles stated in advance: the three known `secrets`
positives MUST fire; the 54 hand-classified `registry` sites and the ~34 `llm-*` +
10 `manifest.toml` hand-classified sites were expected to fire zero. This document
diagnoses why the sweep missed two of three positives and over-fired roughly
thirty-fold, rather than tuning the detector to the oracles after the fact.

**Decision history, recorded in full rather than as a final outcome** (a written
decision reversed only in chat leaves the record saying one thing while the code
says another):

1. First pass (below): **not funded** — the general fix (call-context
   discrimination plus cross-module reach) is a substantial build, and the work
   it would automate is already done by hand.
2. Reversed to **fund two specific, cheaply-measured changes** (a `CADRUMO_*`
   env-var-key signal; excluding four `TAXONOMY_MARKERS` members that are
   injection-parameter names) and retarget the tool to diff-scoped review,
   after a teammate (`honesty`) measured both changes recovering the two known
   misses at low added noise.
3. **Reversed back to not funded**, on a further measurement (below): a random
   sample of the sites the detector silently discards found the dominant real
   miss is not a vocabulary gap at all, so no signal-set tuning — including the
   two changes just funded — closes it. The code for step 2 was implemented,
   then reverted in the same session once step 3 landed; see the commit history
   on `dev/write_site_census.py` for both.

## Findings

### sweep-misses-two-of-three-known-positives-and-over-fires-30x | high | The detector fails its own oracle set on both axes

Run at `64c9fe6d6e`, `--scope tests`: 4557 file-producing sites, 1% unresolved
(34), 114 flagged `constrained`. Against the oracles: `test_bundle_export_recovery.py`
fired correctly; `_registry_cli_fixtures.py` and `test_m145_communication_cli.py`
— the other two known `secrets` positives — did not fire. `registry` produced 3
hits against an expected 0; `llm-*` produced roughly 9 hits (`test_cache.py`,
`test_run_telemetry_retention.py`) against an expected 0. Independently
reproduced at a different pin from a parallel run at `53f80f0830` (110 hits, the
same two misses, the same over-firing shape), so the result is not an artefact of
one revision.

### over-firing-has-three-distinct-mechanisms-all-rooted-in-crude-vocabulary-reuse | high | CONSTRAINT_RISK_SIGNALS answers "is this identifier present" not "is this a real accessor call"

Read a sample of the 114 flags rather than trusting the count. Three distinct,
independently-confirmed causes, none of them the intended signal:

1. **Self-referential accessor tests.** `test_keystore_paths.py` imports and
   calls `keystore_path()` directly, then asserts its return value against a
   literal built the same way (`tmp_path / "keystore" / "alpha"`). The module
   legitimately references the accessor AND legitimately builds taxonomy-shaped
   literals — because it is the accessor's own test — and the detector cannot
   distinguish that from an independent injection agreeing with an unrelated
   consumer.
2. **Generic local-variable names colliding with the marker vocabulary.**
   `test_run_telemetry_retention.py` never calls any accessor. It fires because
   line 157 assigns a local variable literally named `root_dir` — a wholly
   ordinary choice of scratch variable name a test author made — and `root_dir`
   is a member of `TAXONOMY_MARKERS`, reused wholesale as part of
   `CONSTRAINT_RISK_SIGNALS`. `TAXONOMY_MARKERS` was designed for
   `_trace()`/`origin_symbol()`'s narrow root-of-expression resolution; reused
   as a blanket "does this identifier appear anywhere in the module, in any
   binding role" scan, `root_dir`/`store_dir`/`db_dir`/`audit_dir`/`blobs_dir`
   are exactly the short, generic English words a test would pick for an
   unrelated local.
3. **Struct field names colliding with the same vocabulary.** `test_layout.py`
   fires because it reads `paths.db_dir`/`paths.blobs_dir`/`paths.audit_dir` —
   real attribute accesses on an unrelated `BucketPaths`-shaped structure whose
   field names happen to match `TAXONOMY_MARKERS`, matched by the same
   `isinstance(node, ast.Attribute) and node.attr in CONSTRAINT_RISK_SIGNALS`
   branch that was meant to catch a genuine accessor attribute chain.

All three share one root cause: the co-occurrence check treats
`CONSTRAINT_RISK_SIGNALS` membership as sufficient on its own, with no check on
*how* the identifier is bound (a call, a root-of-expression trace target, versus
an arbitrary local or field name). 18 of the 36 flagged files already carry a
`PINNED_TAXONOMY_LITERALS` declaration, which independently confirms the
over-firing concentrates exactly where accessor-and-literal co-occurrence is the
normal, already-handled case, not a novel hazard.

### the-two-misses-have-two-different-independent-causes | medium | One is the documented cross-module limitation firing correctly; the other is a genuine vocabulary gap

`_registry_cli_fixtures.py` injects `str(tmp_path / "secrets")` in a fixture
function and never itself references any accessor, `subprocess`, or `CliRunner`
name — the module docstring's own two mentions of the real mechanism
("`storage_overrides`", "subprocesses") are prose inside a `Constant` string
node, invisible to an `ast.Name`/`ast.Attribute` walk. The real CLI invocation
(`invoke_cached_cli`) lives in the separate consuming module,
`test_registry_cli.py`. This is the documented limitation
("module-local co-occurrence is the whole signal") working exactly as designed
and disclosed — not a defect, but proof the limitation is real and costs a
known true positive.

`test_m145_communication_cli.py` is the sharper case: the injection (line 141)
and the CLI invocation (`invoke_cached_cli`, line 158) are in the **same
module**, yet it still misses, because `invoke_cached_cli` — the project's own
wrapper used by nearly every CLI integration test in this repository, per
`treegates`'s independent observation on the `live`/`runs` bands — is not a
member of `CONSTRAINT_RISK_SIGNALS` (`subprocess`, `Popen`, `CliRunner`, plus
`TAXONOMY_MARKERS`). This is fixable in isolation (add the project's real
invocation wrapper name to the signal set), but fixing it does not touch the
over-firing findings above, which are the dominant failure mode by a wide
margin.

**Correction on second reading:** an earlier round attributed both misses to
the same cross-module cause. `test_m145_communication_cli.py` is same-module —
a missing signal name, not the documented limitation — so "0 for one sub-shape,
1 for the other" rests on a single case, not two. Recorded because the earlier,
narrower reading was relayed onward before this correction landed.

### honesty-measured-the-real-denominator-702-coinciding-519-never-printed | high | Three known positives cannot validate recall; the population that matters is ten times larger

A teammate (`honesty`) walked the archived test tree with this module's own
`_literal_tail`/`_taxonomy_subpath_tokens`/`_module_signals_constraint_risk`
and measured every `temporary`/`pass_through` site whose literal tail coincides
with a declared taxonomy token, independent of whether the risk signal fires:

```
702  coinciding tails, across 187 files
183  module signals risk  (45 files)   -- candidates for a print
519  no signal at all      (142 files) -- silently discarded, never printed
110  flagged constrained  = 16% of the coinciding-tail corpus
```

Two of the three known oracle positives live inside the 519. This retires an
earlier, unmeasured objection to funding any fix ("110 hits is more reading
than the hand-classification cost") — the detector is a roughly 6.4x reduction
of the coinciding-tail population, not an increase in reading, so that
objection would have condemned the tool even at perfect recall. The real
question was never precision; it is whether the 519-site discard pile is safe
to never read.

**Correction, recorded in place rather than silently edited.** This section
previously claimed an independent reproduction at `dcfb8209e4` "confirming"
the instrument — flagged set matching at 110 against a coinciding-tail
population "shrunk" to 307/197, attributed to intervening `S78`
hand-classification commits retiring real sites. **That reconciliation is
false.** `honesty` measured both the `53f80f0830` and `dcfb8209e4` versions of
the detector directly against the `dcfb8209e4` tree and got identical results
from each (`183`/`519`/`702`) — the detector file is byte-identical between the
two pins (`git diff 53f80f0830 dcfb8209e4 -- dev/write_site_census.py` is
empty), and the intervening test-tree churn (11 files, +464/−7, net additive)
cannot retire 212 sites. A cross-check recorded as agreement is exactly the
kind of finding this campaign has learned gets the least scrutiny, because
nobody re-runs a result that already confirms the thesis; this one did not
get that scrutiny before landing, and should have.

What `307`/`197`/`110` actually measures is not yet established. It was
produced by a standalone re-implementation of the walk (not the production
`census()` entry point), and the bug — if it is one — has not been isolated:
the write-call and bare-chain branches were each written to mirror
`write_target`'s and `_top_level_div_chains`'s exact inputs to `_literal_tail`,
but the aggregate count still diverges roughly 2.3x from the same walk run
independently. Left open rather than reconciled to a story a second reading
could not sustain. `honesty`'s own `183` vs `110` gap (a coinciding-tail site
in a risk-signalling module should, by `_is_constrained`'s construction, be
exactly the flagged set) is also unresolved and may share a root cause with
this one. The population figures to cite until this is resolved are
`honesty`'s directly-measured `702`/`519`/`183`/`110`, not the retracted
`307`/`197`.

### sampled-recall-of-the-discard-pile-finds-23-percent-rename-sensitive | critical | The class is not reachable by module-local co-occurrence, and no signal-set tuning fixes that

Per the pre-stated design (a random, not a chosen, sample settles this or it
proves nothing — a hand-picked sample reproduces the three-oracle problem at
scale): `honesty` drew `random.Random(20260804)`, n=30, from the 519-site
discard pile and classified each against the real production code, not the
test snippet alone.

**Correction, recorded in place.** The classification was first reported as 7
of 30 rename-sensitive (5 breaks, 2 voids) without checking enrollment — a
correctly-declared `PINNED_TAXONOMY_LITERALS` pin is *resolved* work (a rename
is supposed to require editing it), not residue. Two of the seven are declared
pins covering the exact sampled site (`test_corpus_text_cache_location.py:42`,
`test_storage_substrate_state_root.py:43`), leaving:

```
                              undeclared-sensitive (real residue)
genuinely constrained -- BREAKS the test                4
silently VOIDS the assertion instead of breaking         1
declared pin (resolved, not residue)                     2
not constrained                                          23
```

**5 of 30 = 16.7%** undeclared rename-sensitive. Point estimate ~87 of 519;
Wilson 95% CI ≈ 7.4%–33.6%, i.e. an estimated 38–174 undeclared rename-
sensitive sites in the pile this check currently never surfaces. (The sample
also spans the whole test tree, not only the narrower `src/cadrumo/tests/`
package some `S78` figures scope to — only 3 of the 30 sites sit inside that
narrower package. If a citation of this figure needs that narrower scope, it
should be re-drawn against it rather than assumed comparable.)

Read against the real callees, the undeclared breaks share one structural
property none of this detector's vocabulary reaches: the segment is
independently derived **inside the production function under test**
(`_profile_bucket_scan`'s own docstring: "Scans every `<root>/buckets/*/manifest.toml`");
the caller's text names no accessor, no subprocess, no marker of any kind —
there is nothing in the calling module to join on. This is a materially
different, and materially larger, failure mode than the vocabulary gap
`invoke_cached_cli` exposed above: **no extension of `CONSTRAINT_RISK_SIGNALS`
can reach a constraint that lives entirely in a callee the detector never
reads.** A proposed fix (adding a `CADRUMO_*` env-var-key string-constant
check, tested against both known misses) was measured to catch 3 of 3 oracles,
but on this sample addresses only the minority mechanism — one of the two
misses caught genuinely, the other incidentally, per a second reading — and
was retracted rather than shipped; see the decision history above and the
revert commit on `dev/write_site_census.py`.

The one undeclared void surfaces a distinct, more dangerous failure mode: a
rename does not break the test, it silently **voids** it — an absence
assertion (`assert not (root / "buckets").exists()`) keeps passing once the
thing it should have caught moved. Precisely stated, this is a **fragility
with a silent-failure mode, not a live defect today**: the guard is correct
and effective at the current taxonomy segment, and only stops working if that
segment is renamed without the assertion being noticed and updated. "A broken
test screams; a voided one does not," and neither is visible to any detector,
including this one, framed around "a rename would break it." Tracked
separately as its own severity category and owned elsewhere in this campaign
rather than duplicated here.

**Caveat on the central claim, stated plainly:** the five undeclared sites
above are classified by reading each callee, not by mutating the taxonomy
segment and running the test — **reasoned, not measured.** A mutation-tested
confirmation of these five, and a check on whether the void pattern is itself
a swept class, is in flight elsewhere in this campaign. This finding's verdict
does not depend on that confirmation (the sample's structural argument —
nothing in the caller to join on — holds from the read alone), but the count
itself should be treated as reasoned until that measurement lands, and this
document updated in place once it does.

## Recommendations

**Final: `WriteSite.constrained` stays retired, at every scope, not funded.**
The recall measurement is the disqualifier the precision estimate never could
be: a random sample of the sites this check silently discards found roughly
17% genuinely rename-sensitive and undeclared, dominated by a mechanism
(production-side derivation) no co-occurrence signal — current or extended —
can reach. A clean tree-wide or
diff-scoped run proves nothing about the population it never printed, so
neither scope is safe to trust as a completeness signal. This supersedes the
mid-session reversal to fund two specific fixes and retarget to diff-scoped
review: that reversal was made on a figure (`CADRUMO_*` catching "3 of 3
oracles") since qualified — one of the three was caught incidentally, per a
second reading — and, more decisively, on a denominator (3 known positives)
too small to validate recall at all. The two fixes were implemented and then
reverted in the same session rather than left half-landed; see the decision
history above.

**The precision figure earlier in this document is an estimate, not a
classification** — "3 real true positives among 114 flags at best" comes from
reading a sample of the flagged output, not from exhaustively classifying it.
Stated here explicitly so a later reader does not cite it as a measured count
the way the recall figure now is.

**Keep the code, the tests, and the honest self-reported unresolved rate.** The
`--scope tests` widening, the `fixture` bucket, import-alias following in
`_bindings()`, and the corrected section header and docstring (naming the
production-side-derivation and vacuous-pass failure modes explicitly, not only
the cross-module limitation) are durable and correct improvements independent
of the funding question. The unit tests for the new primitives (`_literal_tail`,
`_taxonomy_subpath_tokens`, `_module_signals_constraint_risk`, `_is_constrained`,
`_top_level_div_chains`) remain valid pins on those primitives' individual
behaviour; they were never claims about the composed detector's real-world
precision or recall, and this finding does not invalidate them.

**A sharper co-occurrence join would not be enough either.** The earlier
recommendation here said a workable version needs call-context discrimination
plus cross-module reach. The sampled-recall finding sharpens that: the
dominant real mechanism is not a co-occurrence at all — the constraint lives
in the callee's implementation, invisible to any check that reads only the
caller's module. Reaching it would need interprocedural analysis (following
the call into the production function actually deriving the segment), a
materially larger build than either of the two changes attempted here. Not
recommended as a next step; six literal bands are already closed by hand at
zero tooling cost, and the 519-site discard pile's real risk is better
addressed by the direct follow-ups below than by a smarter static scanner.

**Follow-ups, tracked separately rather than duplicated in this document:** a
full sweep for the vacuous-pass pattern (an absence/emptiness assertion that
would keep passing after a taxonomy rename) across the discard pile, and a
mutation-tested (not merely read) confirmation of the five genuinely
rename-sensitive sites this sample found. Both are owned elsewhere in this
campaign.

**The pre-stated oracle discipline is what made every step of this usable
rather than a negotiation, twice over.** "Missing any known positive is
disqualifying" turned 114-flags-for-3-true-positives into a settled question on
contact rather than an argument about tolerable ratios. The same discipline —
"random, not chosen" — is what makes the recall figure load-bearing: a
hand-picked sample would have reproduced the original three-oracle problem at
a different scale, and neither a defender nor a critic could have out-argued
the other from a cherry-picked number.
