---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:477402a74b51f3981ca31ac62e3f590f1071e9df570441f368db8ec91482eb44'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# `test-harness-sanity` audit: harness performance

## Scope

Measured, not estimated. Every figure below came from running the thing; two hypotheses that looked obviously right were checked and disproved, and both are recorded so nobody spends the afternoon re-deriving them.

The subject is what the harness costs to RUN: collection wall-clock, per-worker fixed cost, and per-test setup. Suite correctness is out of scope here.

## Findings

### import-time-side-effect | fixed | One eager registry load cost 3.2x on collection and 21 modules

A shared test-support module resolved a registry revision id in a module-level constant, so importing it loaded and validated the entire registry authority as a side effect of import. That is paid by every module that imports it, whether or not the importer needs a revision id, and it is paid again by every parallel worker.

It became visible only when this campaign's fixture consolidation repointed four further test modules at that support module for its shared taxpayer persona. Each inherited a full authority load it had no use for, and a latent condition became a collection error that killed the module outright.

Resolved on first use rather than at import: collection errors 21 to 2, and full collection 310s to 98s.

The generalisation is the useful part. Expensive work at module scope is charged to IMPORT, and pytest imports during collection, once per worker, for every module in the transitive import graph. A cached function costs the same on first use and nothing on the paths that never touch it.

An AST sweep of all 5580 first-party modules for module-level calls into the expensive entry points now finds two, both in one module already flagged for other reasons. This class is closed rather than merely reduced.

### per-worker-fixed-cost | open, and not this campaign's | Registry validation is recomputed by every worker

A cold registry authority costs **22 seconds per process**, split roughly 5s compiling the authoring tree and 17s validating it.

The compile half is already shared: a fingerprint-keyed disk pickle lets every worker and every subprocess-spawning test read one compiled tree, deliberately enabled under pytest for the bundled read-only tree and deliberately disabled for mutable or synthetic roots, which can be edited mid-run by the very test that built them. That machinery is correct and working.

The validation half is cached nowhere across processes. The suite runs `-n auto` on a 24-CPU machine with `--dist=loadfile`, so every worker that draws a registry-dependent file pays that 17s independently: as much as **7 CPU-minutes of byte-identical validation per suite run**.

The shape of the fix is already in the tree next door — the validation verdict is a pure function of the same tree fingerprint the compile cache already keys on. This belongs to whoever owns the registry package; it is recorded here rather than attempted, because a cache over a validation gate is exactly the kind of change that is easy to make silently permissive.

### disproved | The bundled-tree disk cache is NOT disabled under pytest

Worth recording because the first measurement said it was, and acting on that would have "fixed" working code.

`is_bundled_registry_root` returned False for what looked like the bundled registry root. The predicate was right and the probe was wrong: the bundled root is the `aeat` directory one level below the path being passed. With the real root the cross-process cache is enabled in production and under pytest, exactly as its docstring claims.

A probe that confirms a suspicion deserves the same scrutiny as one that contradicts it.

### disproved | Widening expensive fixture scope would not help

342 fixtures are function-scoped and 163 of those perform expensive setup, which reads as an obvious optimisation and is not one.

The registry authority caches built snapshots per process in its own map, so a function-scoped snapshot fixture returns a cached object after the first build; the scope costs nothing to widen and gains nothing. The remaining expensive function-scoped fixtures construct real encrypted stores, where a fresh store per test IS the isolation contract, and widening their scope would trade a correctness property for no measured time.

The instinct is right in general and wrong here, and the distinguishing question is cheap to ask: does the thing being built already cache, and is per-test freshness load-bearing?

## Recommendations

- Cache the registry validation verdict against the tree fingerprint the compile cache already computes, in the registry package.
- Keep expensive work out of module scope in test-support modules; resolve on first use. This is the one pattern that multiplies across both importers and workers.
- Re-measure worker count against wall-clock once the tree is healthy. `-n auto` yields 24 workers here, and a high per-worker fixed cost can make fewer workers faster; that comparison is not meaningful while a large fraction of tests fail fast for unrelated reasons.

## Notes

Per-test hot spots were not obtained. Two full-lane runs with `--durations` were killed before the summary prints, and durations measured against the current tree would be distorted anyway: a large fraction of tests currently fail fast on a registry gap unrelated to timing, and a failed test is usually a fast one.

**Correction, 2026-08-15.** The second half of that reasoning is half right, and
the difference decides whether the technique is usable at all. A red tree makes a
durations ranking INCOMPLETE — fast failures crowd out slow passing tests, so the
list under-reports — but it does not make the entries on it false. A test that
appears slow IS slow, whatever its neighbours are doing. Durations are therefore a
valid way to FIND targets and an invalid way to rank them exhaustively, and
dismissing the technique because the tree is red throws away evidence that is
sound as far as it goes.

The real obstacle is narrower and mechanical: `--durations` prints only at the end
of a run, so a run that does not finish yields nothing at all. A sequential pass
over `domain/calculations/registry/tests/` was still at 61% after twenty-five
minutes. Splitting the work per module does not rescue it either, because separate
processes each pay the per-process authority load instead of sharing one.

The collection figures above are trustworthy because they do not depend on tests passing.

## Why separate test processes do not share the compiled registry

Asked directly: 24 xdist workers each pay a full authority load, which is the
same derivation 24 times. The reuse machinery for it EXISTS and is correct. It
is starved, and by two independent causes.

**The compile disk cache is starved by tree churn.** `registry_disk_cache_enabled`
returns true, the bundled root is recognised, and the cache directory holds
16.7 MB pickles — eight of them, written across twenty-two minutes under eight
different keys, none ever read back. The key is the registry tree fingerprint,
and 52 files under `_data/registry/aeat/legal/` were dirty and being edited by
other agents while these runs happened. A changed tree SHOULD miss, so the cache
is behaving correctly; it simply never sees the same tree twice.

Proven by removing the churn rather than by argument. Against a `git archive HEAD`
snapshot of `_data`, which cannot move, three separate processes compiled in
29.77s, 9.94s and 8.36s: the first populates, the rest reuse. Cross-process
sharing works.

**The validation verdict cache is starved by the tree being red.**
`registry_validation_is_certified` skips `validate_registry` entirely on a hit,
and `certify_registry_validation` writes a verdict only on a GREEN outcome.
Neither the writable verdict
(`…/cache/registry-verdict/cadrumo_validation_verdict_*.json`) nor the shipped
one (`_data/registry/aeat-validation-verdict.json`) exists, because this tree
fails validation. So every process re-runs validation in full, and will keep
doing so until the registry lane's failures are cleared. That is roughly half
the load and it is not cacheable from here.

## A cache HIT was itself paying for a path-part walk

The snapshot runs exposed something the churn had been hiding: even a hit cost
8-10s. Profiling one showed `is_bundled_registry_path` at 4.7s of a 14.7s warm
compile. It is asked about every registry TOML — 17,234 times — and answered
with `Path.is_relative_to`, roughly a quarter of a millisecond per call on
Windows, deciding the same containment question against a root that cannot
change during the process.

Replaced by a normcased string prefix comparison, memoised once:

    warm compile                  14.678s -> 8.991s   (-39%)
    function calls             16,477,054 -> 5,039,574 (-69%)
    collect_cached (fingerprints)  9.834s -> 4.393s
    _toml_content_digest           7.793s -> 2.274s

Equivalence proven against the previous implementation on all 17,273 registry
TOML paths and on adversarial cases: the root itself, its parent, an `aeat-old`
sibling whose name prefixes the root, an `aeatx` sibling, an upper-cased
spelling, and an unrelated absolute path. Zero mismatches.

The code landed in `459db261e2`, a peer's broad commit that captured the working
tree before this session could commit it under its own message. Recorded here
because the measurement and the equivalence proof are otherwise unattached to
the change.

## Correcting my own scandir claim: the win is pruning, not the primitive

A commit message of mine states that replacing `Path.rglob` with `os.scandir`
made the source-tree walk about ten times faster. That number is real and the
attribution is wrong, which matters because it points the next reader at the
wrong lever.

Measured on Python 3.13.11, over `src/cadrumo`, separating the two variables:

    rglob, primitive only            4,981 files   0.386-0.415s
    scandir, primitive only          4,981 files   0.249-0.276s
    rglob + Python-level filtering    4,977 files   0.376s
    scandir + directory pruning       4,977 files   0.024s

The primitive alone is about 1.5x, not ten. Python 3.13 rewrote globbing onto
`os.scandir` and closed most of the gap that older advice assumes. The ~16x
comes from PRUNING: refusing to descend into `__pycache__` and `_data` at all,
which `rglob` cannot express -- it can only filter paths after walking them, so
the subtree is traversed either way.

The original measurement compared "rglob plus a Python filter over every path"
against "scandir with pruning", which conflated the two variables and credited
the faster primitive with the pruning's saving.

Two things follow. Migrating a walk to `scandir` for its own sake buys little;
migrating it so the walk can PRUNE buys a lot. And a caller that must inspect
every file anyway should expect no gain from the change at all.

Found because a peer, migrating this code onto the shared
`cadrumo.core.scan_directory` primitive, wrote the correct attribution into its
docstring and contradicted the claim. Verified here rather than taken on trust,
and the peer is right.

## The compiled registry was loaded 66 times across the test suite

`load_registry_tree` carries no memo of its own. Four consecutive calls in one
process measured 15.62s, 3.10s, 4.67s and 15.29s: the spread is the
fingerprint-keyed disk cache hitting or missing as peers edit the tree, and the
floor is never free. The suite held 66 such call sites across 45 test modules,
35 of them outside the registry package where the existing session-scoped
`registry_tree` fixture cannot reach. `test_source_resolver` alone made 15
identical calls; `test_m303_orden_anual_authority` made 9 while the fixture that
makes the same call sat one directory up, unused.

Both are now migrated -- the second onto the existing fixture, the first onto a
new `cadrumo.tests.registry_tree.bundled_registry_tree()` importable from any
package.

Two properties make sharing one compiled tree safe, and both were checked rather
than assumed. The accessor takes no arguments, so it holds exactly one entry and
cannot answer for a different root; a test loading its own tree keeps calling the
uncached function. And `ModeloDefinition` and `RegistryCatalogues` are declared
`frozen`, so an attribute write raises -- handing every caller the same objects
is safe by construction rather than by convention. Were they mutable this would
be a hazard, because one test's edit would reach every later test in the worker.

One failure in the migrated module was NOT caused by the sharing, and the
distinction mattered: modelo 390 carries revisions 2022-2025 while the test asks
for 2026, which raises `NoRevisionForPeriodError` identically under a direct
uncached load. A shared-object bug would have looked the same from the test's
side, so it was reproduced against the uncached path before being dismissed.

Recorded here because the change landed inside `c180fe8e6e`, a peer's broad
commit that captured the working tree before this session could commit it under
its own message. That is the third such sweep today.

## Correction: the "66 to 2" migration count measured a narrower set than it named

An earlier round of this campaign reported the direct bundled-root
`load_registry_tree` call sites reduced from 66 to 2. That number is real but its
SCOPE was mis-stated. The census behind it enumerated `test_*.py` modules only.
The `_*_support.py` helper modules, the package `conftest.py` files and
`cadrumo/tests/registry_observations.py` were never in the denominator, so they
could not appear in the remainder either.

The honest count at the time of the correction is 13 test-layer files, not 2. The
failure is the familiar one of a measured claim about a set generalising into an
unmeasured claim about everything of that kind: the instrument's reach silently
became the claim's scope. What makes it detectable is that the report named a
population ("call sites") broader than the glob that produced it.

Re-measured with a call-form-agnostic multiline pattern over `src/**/*.py`, then
classified rather than totalled, because the two classes have different
dispositions.

## The warm cost of a registry load is the walk BEFORE the cache lookup

`load_registry_tree` is backed by `_load_registry_tree_cached`, an `lru_cache`
keyed on `(root, fingerprints)`. That framing hides the real cost: the function
resolves the root, validates the legal directory, discovers modelo sources and
collects the whole tree's fingerprints BEFORE it can compute the key. All of
that runs on a cache HIT.

Measured in one warm process, six consecutive calls on the bundled root:

    2.2439s  1.0072s  1.2641s  1.0552s  1.1671s  1.0648s

So the steady-state price of a fully-cached load is ~1.05s. Against the shared
accessor in the same shape:

    2.866456s  0.000002s  0.000000s  0.000000s  0.000000s  0.000000s

The comparison is what makes the lever visible. Reading the code alone suggests
repeat calls are already free, and they are not; reading the first call alone
suggests the load is simply expensive, which conceals that the recurring cost is
avoidable. Both readings are wrong in the same direction.

## Nineteen PRODUCTION call sites pay that walk, unmemoised

The classification pass turned up something outside this campaign's remit and
worth stating plainly: 19 non-test modules call
`load_registry_tree(bundled_path("registry", "aeat"))` directly, and a sample of
four (`_calculate_input.py`, `_binding_prefill.py`, `_projection.py`,
`_observations_repository.py`) carries no memo of its own.

The sharpest of these is
`application/calculations/_observations_repository.py:437`,
`_validate_observation_casilla_ids(observation)`. It takes a SINGLE observation
and is invoked once per `save`, so persisting N observations pays N full tree
walks at ~1.05s each. This is a live calculation path, not a test.

NOT acted on, deliberately. The test-layer accessor lives in `cadrumo.tests` and
production must not import it, so the remedy is a production-side memo, which
intersects `aeat-registry-authority-flow` (these paths arguably should reach the
authority rather than the raw loader at all). That is an owner's decision and a
different lane. Recorded so it is not lost, and so the next reader does not have
to rediscover the per-observation shape.

## Migrating the helpers also closed a private-import violation

Two of the twelve migrated helpers --
`application/calculations/tests/_iva_compensation_history_support.py` and
`_cross_period_clean_state_support.py` -- reached `load_registry_tree` through
`....domain.calculations.registry._loader`, a cross-package PRIVATE submodule
import that `aeat-architecture-boundaries` forbids. Routing them through the
shared accessor removes the private reach as a side effect. Noted because it was
not the goal, and an incidental fix that nobody records is one somebody later
re-introduces.

## The import surgery was driven from the AST, after three text-anchor failures

Earlier rounds broke three ways on textual anchors: a relative-depth off-by-one
(reaching `cadrumo` from `cadrumo.a.b.tests` needs FOUR dots, because one dot is
the current package), an insertion landing inside a parenthesised
`from x import (` block, and an insertion landing inside a module docstring whose
prose line began "from a list maintained by hand".

The migration script therefore takes every position from real AST nodes, derives
the dot-depth from the file's own existing relative import rather than counting
path segments, and drops an import name only when the AST reports zero remaining
`Name` loads of it. It then re-parses and refuses to write unless the accessor is
imported exactly once, is actually called, and no docstring contains the import
text. A dry-run diff was read before applying.

## Attribution: a PRE-MIGRATION snapshot, not a plausibility argument

A wide slice (registry tests plus calculations tests) reported 1723 failed, 3443
passed, 229 errors after the helper migration. That number cannot be read as
evidence either way on its own, because this tree carries a large standing red
(missing export layouts, blocked `authority_grade`, legal grounding) that
predates the change.

Reasoning about it was not accepted as attribution. `git archive f38ed9ade9^ |
tar -x` produced an immovable pre-migration tree in scratch -- immovable
mattering because peers commit to this worktree continuously -- and the same
three consumer modules were run against both trees, the snapshot reached through
a `PYTHONPATH` shadow whose effect was CONFIRMED before use (`cadrumo.__file__`
resolves inside the snapshot) rather than assumed.

    pre-migration : 33 failed, 31 passed
    migrated      : 33 failed, 31 passed

Counts alone would not have settled it, since a count cannot distinguish one
failure being fixed while another appears. The failing test NAME SETS were
diffed and are identical. The migration is behaviour-neutral, and the wide
slice's 1723 failures belong to the standing red.

Wall clock on that slice moved 80.82s to 51.06s, recorded as indicative only:
the machine was carrying about 90 concurrent python processes from peer suites,
and contention invalidates timing. The durable measurement is the per-call one
(~1.05s to ~0s) and the structural one (one compiled tree per process instead of
one per helper module).

## Payload identity, checked rather than argued

`bundled_registry_tree()` and `load_registry_tree(bundled_path("registry",
"aeat"))` were compared directly: equal modelo count (73), equal modelos, equal
catalogues, and `a_m is b_m` True -- the accessor hands back the very same
objects, not a reconstruction. The alternate call form
`load_registry_tree(bundled_path() / "registry" / "aeat")`, which one migrated
module used, resolves to the same tree and compares equal, which is what makes
substituting the accessor there sound rather than merely plausible.

## Ruled out: the disk-cache fingerprint module keeps its direct load

`domain/calculations/registry/tests/test_registry_disk_cache_loader_fingerprint.py:287`
is the one test-layer bundled-root load left standing, and it stays standing.

`test_every_foreign_type_in_the_compiled_payload_is_covered_by_the_derivation`
walks the real compiled payload's object graph as the GROUND TRUTH the
annotation-driven derivation is measured against. Routing that read through a
test-owned cached accessor would make the oracle depend on the accessor
continuing to mean "the real bundled tree" -- and if a later change ever pointed
the accessor elsewhere, the oracle would silently measure the wrong tree while
still passing. The module also owns the disk-cache poison test, which
deliberately calls `cache_clear()` and must keep talking to the loader directly.

The saving forgone is one tree walk in one test. Not worth laundering an oracle
through an indirection whose whole value is that it is shared and therefore
changeable by someone else.

## Round: the `src/cadrumo/tests` durations slice, re-measured

The targets carried forward from the previous round were stale, and re-running
`--durations` before acting is what caught it:

    recorded          re-measured
    145.6s   ->       105.84s  test_acceptance_wall_catalogue (setup)
    120.8s   ->        90.17s  test_wheel_content_boundary (setup)
    102.3s   ->        57.44s  test_full_corpus_collectability_harness (call)

Acting on the recorded figures would have meant optimising a ranking that no
longer held. Re-measuring also surfaced a target absent from the carried list
entirely, and it was second overall: `test_dev_audit_report.py` setup at 91.43s.

### Fixed: the shadowing dimension was scanned three times

`audit_shadowing()` runs the real Family-3 scanner over the live tree. Measured
standalone at 14.86s and 15.52s across two calls -- it carries no memo.
`test_dev_audit_report.py` invoked it THREE times: twice standalone
(`test_audit_shadowing_returns_a_valid_dimension_report` and
`test_audit_shadowing_red_findings_are_never_in_the_tolerated_baseline`) and once
more inside `build_report`, which the module-scoped `live_health_report` fixture
already ran.

Both standalone calls now read the dimension out of the composed report. This is
sound rather than merely convenient: `build_report` places the
`audit_shadowing()` return value into its tuple UNCHANGED -- no projection, no
copy -- so `_dimension(report, "shadowing")` yields the identical object the
standalone call produced, including `details`, which the baseline test reads.
That was checked in the source before the edit, not assumed from the shape.

Measured on the whole module, each configuration run twice:

    before : 128.80s, 135.18s
    after  :  91.51s,  94.27s

Roughly 30% off, and 12 passed in all four runs. The before-figures come from a
`git archive HEAD` snapshot reached through a confirmed `PYTHONPATH` shadow, so
both configurations measure the same tree except for the one file.

This is the same lever that previously collapsed the complexity and duplication
dimensions in this module; shadowing was simply missed at the time because only
the two dimensions named in the durations table were examined. Worth stating as
a pattern: when one composed report is already being built, EVERY standalone
re-derivation of one of its parts is redundant, not just the expensive ones that
happened to rank.

### Ruled out this round, with the measurement that ruled them out

`test_acceptance_wall_catalogue` (105.84s setup) -- ALREADY optimised. Its 30
catalogued walls were previously collapsed from ~30 cold pytest boots into ONE
shared subprocess boot. What remains is the batched subprocess actually
EXECUTING 30 integration wall tests, which is precisely what the gate exists to
prove. There is no duplication left to remove; the cost is the evidence.

`test_full_corpus_collectability_harness` (57.44s) -- inherent. It runs a single
subprocess collecting the entire ~29,600-test corpus. It was checked for the
obvious defect (one subprocess per root) and does not have it: `collection_report`
passes every target to one invocation. The second caller of `collection_report`
is a bounded scratch control, not a second full collection.

`tracked_test_files` -- MEASURED at ~0.08s per call (3216 files via `git
ls-files`), uncached, with five call sites. Caching it would save well under a
second while freezing an answer the harness currently re-reads from git on
purpose. Not worth the staleness surface. Recorded so the "it spawns a
subprocess, therefore cache it" reflex is not re-chased on the next pass.

`audit_layering` -- MEASURED at 1.51s and 1.25s. Called twice. Left alone; the
standalone call in `test_audit_layering_evaluates_every_declared_contract` is
cheap enough that routing it through the fixture buys nothing and costs a
coupling.

### Fixed: the drift census ran five times for one answer

`dev.quality.regulatory_drift_census.census()` scans the production tree,
measured at 18.96s / 19.50s / 20.01s across three calls (603 findings), and
carries no memo. `test_the_detector_recovers_known_regulatory_data` is
parametrized over five `_KNOWN_INSTANCES` entries and called `census()` in the
test body -- so it ran the full scan five times to produce an answer that does
not vary with the parameters at all. Every case filters the SAME result by path
and kind.

A module-scoped fixture now runs it once. Per-test durations, which are the
trustworthy signal here because the machine is under peer load:

    before : 26.38s, 24.94s, 23.78s, 21.99s calls (fifth below the cutoff)
    after  : one 22.33s setup, every case below the cutoff

### The optimisation that would have broken the gate

The obvious move -- put `@cache` on `census()` at its definition -- is WRONG and
was rejected. `test_the_census_reproduces_itself_exactly` calls `census()` twice
and asserts the results are equal, which is a real non-determinism gate. Memoise
the function and both calls return the SAME OBJECT, so the assertion compares a
thing with itself and holds no matter how unstable the census becomes. The test
would go green and stay green while measuring nothing.

So the fixture is scoped to the parametrized recovery cases only, and the
reproducibility test still calls the unmemoised function twice. Its duration
after the change is 38.62s, still about two census runs, which is the
confirmation that its two independent scans survived rather than a hope that
they did.

Worth generalising: in a suite full of "run the expensive thing once and share
it" wins, the one place sharing must NOT reach is a test whose subject is
whether two independent runs agree. Redundant work and the measurement of
redundancy look identical from the durations table.

Wall clock across repeats was 181.97s / 222.37s before and 147.82s / 121.65s
after -- a wide spread in both configurations, which is why the per-test
structural figure (five census runs to one) is reported as the result and the
wall clock only as corroboration. One pre-existing failure,
`test_every_finding_carries_exactly_one_adjudication`, reproduces identically in
both configurations; it goes through `reconcile()` and was not touched.

## Round: locale catalogues and the IVA stem gates

### The largest single win of the campaign: 125s to 6s

`test_locale_translation_honesty` measured 125.14s / 126.13s and was, almost
entirely, YAML parsing. The four shipped catalogues are ~3 MB each and
pure-Python parsing measured ~7s apiece; five gates read the same four files
roughly nineteen times between them. The per-test durations matched the parse
count exactly, which is what identified the cause rather than merely the
symptom:

    28.21s, 28.62s, 29.55s, 30.83s   four-locale sweeps  (4 parses each)
     7.07s                           single-locale gate  (1 parse)

Two levers, stacked. The parse is now memoised per locale, and it uses
`yaml.CSafeLoader` -- libyaml, the C parser -- measured at 0.773s against
7.402s on the largest catalogue, a 9.6x primitive speedup. The pure-Python
fallback is retained for a PyYAML built without libyaml. Both loaders were
confirmed to produce EQUAL documents for all four shipped locales before the
switch; a 9.6x faster parser that disagreed on one value would be a
correctness regression wearing a performance result.

    before : 125.14s, 126.13s
    after  :   6.86s,   6.04s

The production renderer in `core.i18n` was already doing exactly this
(`_render.py:562` picks `CSafeLoader` when present, behind an `lru_cache`), so
the test harness was the laggard, not the application. Worth noting for the
next reader: the fast path already existed in the tree and simply had not
reached this gate.

The gate's parse stays INDEPENDENT of that production reader deliberately. These
gates assert what the shipped FILES contain; borrowing the production reader
would let a reader that silently dropped entries certify its own view of the
catalogue instead of the catalogue. Speed was taken; independence was not
traded for it.

### The IVA stem gates: fused, not cached

`test_spanish_iva_stem_conformance` ran three gates that each walked
`src/cadrumo` and `ast.parse`d all 4903 modules -- 15.56s, 18.70s and 22.40s.
The parse is identical across the three; only the analysis differs.

The obvious fix -- cache the parsed trees and hand them out -- was MEASURED and
rejected: parsing all 4903 files at once holds **1247 MB** of AST, and under
`-n auto` that is per worker. This is the same shape as the tree-wide AST cache
this campaign already ruled out for measuring SLOWER than re-parsing; the memory
figure explains why that happened rather than leaving it as folklore.

Instead the three analyses now run over each tree while it is live, and the tree
is dropped. Only findings survive, which are small. Each gate keeps its own test
and its own assertion, so a failure still names the gate.

    before : 76.16s, 63.00s
    after  : 48.92s, 49.48s

Less than the 3x a naive reading predicts, because the per-tree `ast.walk`
analyses are themselves a large share of the cost -- only the parse was
duplicated, not the analysis.

### The equivalence check that a test count would have passed

Both configurations reported "2 failed, 3 passed" with the same two test names,
which is exactly the evidence that is NOT sufficient: a refactored analysis can
fail the same test for a different reason. pytest's own rendering then showed a
violation entry present after and absent before -- which looked like a real
divergence and was in fact truncation of a differently-worded assertion
expression.

Rather than judge that from the rendering, a driver ran the three separate
passes and the fused pass against the same tree, through the same helpers and
constants, and compared all five outputs exactly:

    path_and_identifier      10 / 10   identical
    identity_tokens           0 /  0   identical
    prose                     1 /  1   identical
    used_external_values      9 /  9   identical
    used_external_fragments   2 /  2   identical

with an anti-vacuity guard that exits non-zero if every list is empty, since an
all-empty comparison agrees no matter what the code does. The `identity_tokens`
row being legitimately 0 is precisely why that guard is needed: one empty pair
proves nothing on its own and only the populated rows carry the result.

## Round: the import-hygiene gate, and two levers correctly declined

### Fixed: one package scan serving forty-three gates

`test_import_hygiene_gate` opened seven of its gates with a byte-identical walk
of the shipped package, and five of those then ran an identical
`walk_module_imports` pass over the result. That pass measured 18.16s and 18.25s
on two consecutive calls -- no memo -- and `_current_production_family1_sites`
alone was called by two different tests, each paying it in full.

Both stages are now memoised once per process, with thin wrappers handing each
caller a fresh `list` rather than the cached tuple, so no gate's arguments
change type and none inherits a sequence another gate could mutate. Copying
~4900 paths costs microseconds against an 18s scan.

    before : 248.81s, 262.89s
    after  : 116.04s, 100.93s

Roughly 2.4x, with the SAME seven failures by name -- the sets were diffed, not
counted, because a refactor can fail the same count for different reasons.

### The baseline that was not a baseline

The first attempt at a before-figure snapshotted `HEAD` and measured 125.10s --
suspiciously close to the after-figure. The snapshot's own guard explained it:
the check printed 3 where 0 was expected, because a peer's sweep had already
captured the edit mid-session, so `HEAD` CONTAINED the change. That "baseline"
was re-measuring the optimisation against itself and would have reported a
worthless 7% improvement as the result.

The fix was to find the first commit carrying the new helper by walking the
file's history and testing each revision's content, then snapshot its PARENT
(`a295ac3032`). Recorded because in this worktree `HEAD` is not a safe stand-in
for "before" at any point -- peers commit continuously, and a snapshot taken for
attribution needs a positive check that it lacks the change, not an assumption
that it does.

### Declined: `test_tax_id_respelling_gate` (22.39s setup + 21.83s call)

Looks like textbook duplication -- a module-scoped `findings` fixture runs
`census("HEAD")`, and `test_the_scanner_reaches_a_real_population` runs it AGAIN.
It is not duplication. That test asserts `findings == scanned`, so the second
run is a determinism check, and a memo on `census` (or reusing the fixture)
would make it compare an object with itself and pass however unstable the
scanner became.

This is the same shape as the drift-census trap recorded above, and it is now
the second instance, which makes it a class rather than an anecdote: a
module-scoped fixture PLUS a direct call to the same function is a determinism
pair until proven otherwise. Read what the second result is compared against
before removing it.

### Declined: `test_tui_migration_manifest` (42.70s, single test)

The test generates the manifest and then INDEPENDENTLY walks and AST-parses the
same modules, asserting the two agree. The duplicated work is the oracle: one
side generated, one side directly measured. Removing it would leave the manifest
being compared to itself.

Separately, `generate_tui_migration_manifest()` currently raises
`TuiMigrationManifestError` on a digest mismatch, which is this module's
standing failure and a tree-state matter, not a performance one.

### Already optimised, left alone: `test_storage_provenance_gate` (34.30s)

Its scan is already `@cache`d at module level; the 34.30s is simply the first
caller paying the shared cost. Nothing to collapse.

## Round: the C scanner reaches the locale MANAGER

The catalogue-parser win recorded above was applied inside one test module. The
same lever was then found one layer down, in `dev/locales/manager.py`, where
`StrictUniqueKeyLoader` -- the parser every locale reader and the whole
`dev.locales` CLI goes through -- subclassed PyYAML's PYTHON `SafeLoader`.

    pure Python base : 9.016s
    libyaml C base   : 0.865s

10.4x, on a parse that every catalogue read pays.

### Why the duplicate-key gate survives the swap

The obvious objection is that `StrictUniqueKeyLoader` exists to REFUSE duplicate
keys, and swapping its base for a C parser could quietly drop that. It does not,
for a structural reason worth writing down: libyaml accelerates only scanning
and parsing. `construct_mapping` is Python in both bases and still runs for
every mapping node, which is exactly where the duplicate check lives.

That reasoning was still not accepted on its own. Before the swap, both bases
were run against the largest shipped catalogue (equal documents) AND against a
planted duplicate key, where both raised `LocaleError` with the identical
message and the identical line number. A faster parser that stopped refusing
duplicates would have traded this module's entire purpose for speed, and the
locale rules depend on that refusal.

The base is selected with `getattr(yaml, "CSafeLoader", yaml.SafeLoader)`, so a
PyYAML built without libyaml still works -- the same shape `core.i18n` already
uses. No caller anywhere depends on the loader's base class; that was checked
rather than assumed.

    dev/locales/tests : 281.59s before, 136.96s / 148.00s after

with IDENTICAL failure sets by name (5 failed, 54 passed both sides).

### A knock-on nobody had to ask for

`src/cadrumo/tests/test_parity.py` reads catalogues through this manager. Its
`test_codebase_to_locale_parity` setup fell from 53.64s to 24.36s with no change
to that module at all. Fixing a shared primitive beat fixing its callers one at
a time -- the opposite conclusion to the earlier rounds, where the sharing had
to be built per module because no shared primitive existed.

### Measured, assessed, NOT taken: memoising `get_codebase_keys`

`LocaleManager.get_codebase_keys()` measured 15.00s then 9.06s and 9.08s -- so
something inside is cached and the bulk is not -- returning 41,926 keys. It is
called by `scaffold()`, by `audit()` and by several parity tests, so a
process-level memo keyed on `src_dir` looks like an easy multi-call win.

Not taken, deliberately. Fourteen sites construct a `LocaleManager`, and roughly
twelve of them build one over a `tmp_path` src_dir into which the test has
PLANTED source files. Across tests that is safe, because pytest hands each test
a unique `tmp_path`; within one test it is not, if the test plants, scans,
plants again and re-scans expecting the new key.

Establishing which of those twelve do that is a real audit, and the failure mode
of getting it wrong is the worst kind this campaign has catalogued: a cached
scan makes a locale gate pass over stale keys, silently. Recorded with the
measurement so the next pass starts from the number and the hazard rather than
rediscovering both.

## Round: the `get_codebase_keys` memo, taken safely

The previous round measured `LocaleManager.get_codebase_keys()` at ~9s a call
(41,926 keys) and DECLINED to memoise it, because roughly twelve of the fourteen
construction sites build a manager over a planted temporary source tree and a
process-level memo keyed on `src_dir` could serve stale keys to a locale gate.

The declination was right about the hazard and wrong about the only available
shape. A memo scoped to the INSTANCE is safe by construction: it cannot outlive
the object whose `src_dir` it describes, a caller wanting a fresh scan simply
builds a new manager, and no keying scheme has to be trusted. That removes the
twelve-site audit entirely rather than performing it.

Two facts make it sound, and both were checked rather than assumed:

- `get_codebase_keys` reads SOURCE while `scaffold()` writes CATALOGUES, so the
  answer cannot move across `scaffold()`-then-`audit()` -- the one sequence that
  calls it twice on one manager, and the reason
  `test_scaffold_surfaces_fstring_registry_keys_as_missing` paid ~9s twice.
- An AST scan of every function constructing a manager found **34 such
  functions and ZERO** issuing a filesystem mutation after construction. So no
  instance is asked twice across a source change.

A fresh `set` is returned per call: the memo holds a `frozenset`, and a planted
mutation on one caller's result was confirmed NOT to reach the next caller.

### The wall-clock figure that had to be withdrawn

A first before/after read 193.25s against 130.25s on `test_parity.py` and was
NOT reported, because re-running it did not reproduce: the failure set moved
between runs, and at one point the module reported FEWER failures than its own
baseline. Peers were committing fixes to the catalogues throughout, so the two
runs had measured two different trees.

A frozen A/B was built instead -- two copies of one `HEAD`, identical except
that the control has the memo's read and write stripped -- which removes tree
drift entirely. It reported 257.39s without the memo and 273.95s with it: no
signal, and if anything backwards. Under peer load this machine's run-to-run
variance on that module is larger than the effect being measured, so NO wall
clock figure for this change is defensible.

The effect was then measured directly, in-process, where a shared clock and a
shared cache state make the comparison sound:

    without the memo : scan 1 = 48.17s, scan 2 = 18.12s
    with the memo    : scan 1 = 19.58s, scan 2 =  0.00s

The second scan is what this change removes, and it costs 18.12s. Both
configurations were instrumented to COUNT invocations as well as time them, and
both report exactly 2 -- so the memo is proven to be exercised on this path
rather than merely present, which the wall clock could not have established
either way.

Correctness is separately confirmed: the frozen A/B produced IDENTICAL failure
sets (5 failed, 27 passed on both sides), which is the one thing those noisy
runs were reliable for.

### Two instrument failures in one round, both caught by their own guards

The first scan for "functions mutating the filesystem after constructing a
manager" reported a clean zero. It had found **zero files** to scan -- a shell
quoting error had emptied the file list -- so the clean result was vacuous. It
was caught only because the rewritten scan asserted its own denominator and
refused to print a verdict over an empty corpus. A clean result and a broken
instrument are the same output; only the denominator separates them.

The second is subtler and worth carrying. The guard confirming a baseline
snapshot LACKED this change grepped for `_codebase_keys` -- which is a SUBSTRING
of `get_codebase_keys`, the method that has existed all along. Every revision in
history "contained" it, including a snapshot from a week before the change
existed. The guard reported "already swept" for every commit it was pointed at,
and would have reported it just as confidently for a tree that predated the work
by a month.

The conclusion it reached happened to be correct, which is exactly what makes it
dangerous: a guard that is right by luck is indistinguishable from one that
works until the day it is not. Pinned by re-checking with `self._codebase_keys`,
which is 4 in the working copy and 0 a week earlier. A guard against a private
attribute must match the attribute, not a fragment of a public method's name.

## Round: the remaining `src/cadrumo/tests` targets are already shared

This round produced NO change, and that is the result. The four untouched
targets left in the durations table were each investigated and each is already
optimally shared; recording why, with the evidence, so the next pass does not
re-derive it.

**`test_facade_export_gate` (41.96s setup).** A module-scoped `head_scan`
fixture already serves four checks from one scan. The remaining `scan()` calls
were checked and every one takes a DIFFERENT revision -- the resolved HEAD, a
historical break revision, and three against a temporary fixture repository --
so there is no duplicate input to collapse. It also reads GIT BLOBS rather than
the working tree, which is the point of the gate, so it cannot borrow the
filesystem AST cache at all.

**`test_no_broad_exception_raises` (40.08s setup), `test_mock_inventory`
(37.25s setup), `test_loopback_llm_singularity` (57.01s).** All three already
request the session-scoped `source_tree_ast` fixture and resolve trees through
`ast_for_path`. Their large SETUP figures are not per-module work at all: they
are the one session-wide prime, attributed by pytest to whichever test in that
worker happened to trigger it first. Reading the durations table naively here
would have produced three "fixes" for one cost that is already shared by every
structural gate in the worker.

That is worth stating as a reading rule. A large `setup` number attributed to a
test that requests a SESSION-scoped fixture is a bill, not a location. The work
belongs to the fixture and is already amortised; optimising the named test is
optimising the wrong thing.

### The shared prime, quantified

Since the prime now underpins most of this slice, it was measured rather than
left as an assumption:

    package_python_files() : 4906 modules
    prime                  : 67.9s, holding 1216 MB
    at the 6-worker default: ~7.3 GB across the run

That is a deliberate and, on the evidence, correct trade: roughly forty
structural gates would otherwise each re-parse the tree at ~15-20s apiece, so
the prime repays itself several times over within one worker. It is recorded
because the cost is real, invisible in any single duration, and would matter on
a machine narrower than this one (24 cores, 137 GB). The worker cap of 6 already
exists for exactly this class of pressure -- its own docstring cites workers
crashing mid-run -- so the two policies are coupled: raising
`CADRUMO_PYTEST_WORKERS` also multiplies this 1.2 GB.

This is also the missing half of the earlier ruling against a tree-wide AST
cache. That ruling stands for a cache built PER MODULE; the session-scoped
version is the shape that works, because one prime is amortised over every gate
instead of one being paid per gate.

### State of the slice

With this round, the `src/cadrumo/tests` durations table has no remaining
target whose cost is duplicated work. What remains is either genuinely
irreducible (a gate executing the thing it certifies), already shared, or an
oracle whose duplication IS the measurement. Further wins in this campaign have
to come from elsewhere: the nineteen production `load_registry_tree` sites
recorded above, which need an owner's decision, or a slice this campaign has not
yet profiled.

## Ruled out: making the session AST prime lazy, and grouping its consumers

Two levers on the 67.9s / 1216 MB session prime were considered and both
declined. Recording the arithmetic and the blocking constraint so neither is
re-derived.

### Lazy priming -- blocked by a gate that exists to prevent exactly this

The prime eagerly parses all 4906 package modules, while
`_parsed_ast_for_path` ALREADY memoises on demand. So the fixture could return
an empty mapping and let `ast_for_path` fill the process cache lazily, and a
worker running only narrow gates would parse only what it touches rather than
the whole tree.

It cannot be done, and the reason is a credit to whoever wrote the gate.
`src/cadrumo/tests/test_shared_source_corpus_floor.py:66` asserts
`len(source_tree_ast) > _COLLAPSE_FLOOR` -- a dedicated tripwire against the
shared corpus silently collapsing to nothing. Lazy priming empties that mapping
at fixture time and trips it. Two further gates
(`test_system_built_prose_elides.py:149`,
`test_advisory_message_constructibility.py:186`) iterate
`source_tree_ast.items()` directly and would simply scan nothing.

The tempting repair -- keep the mapping lazy but report a full `__len__` -- is
the worst option available: it makes the floor gate pass while measuring
nothing, converting a working tripwire into decoration. The eager prime is a
CONTRACT, not an implementation detail, and three gates depend on it.

### Grouping the 47 consumers onto one worker -- worse on the axis that binds

47 test files request the fixture. Under `--dist=loadfile` at the 6-worker
default they spread across all six, so six workers each pay 67.9s and hold
1216 MB: ~407s of CPU and ~7.3 GB in aggregate. Forcing them onto one worker
with an xdist group would cut that to one prime and 1.2 GB.

It would also serialise 47 structural gates onto a single worker while the other
five drain early, making that worker the long pole. The trade is CPU and memory
against wall clock, and memory is not the binding constraint on this machine
(24 cores, 137 GB, ~50 GB free even under peer load). At six workers the prime
amortises over roughly eight gate files each, which is already a good ratio.

Both stay declined unless the worker cap rises materially -- at which point the
memory arithmetic changes and this entry is the place to start.

## Aborted: profiling the `dev` slice under peer load

An attempt to profile the `dev` tree for fresh targets was started and then
STOPPED rather than allowed to finish. It reached roughly 80% in about fifty
minutes, then produced no further output for seventeen. The machine was carrying
161 concurrent python processes from peer suites at the time.

Stopped rather than waited out, for two reasons. A durations table gathered
under that load would rank tests by who was starved rather than by what costs,
and this campaign has already had to withdraw one figure taken in exactly those
conditions. And the run was itself contributing to the load it was being
distorted by.

No targeting conclusions are drawn from the partial output, and it was deleted
rather than kept, because a partial durations file invites exactly the "the top
entry is the slowest test" reading it cannot support.

The `dev` slice therefore remains UNPROFILED, which is a different state from
"profiled and clean". Recorded so the next pass knows there is no data here yet
rather than assuming an absent entry means nothing was found. Retry when the box
is quiet; `dev/locales` is the only part of `dev` this campaign has measured.

## Round: an invocation counter for a contended box, and what it got wrong

With the machine carrying ~190 competing python processes at 99.7% CPU, a
durations table ranks tests by which were starved. So this round used a
different instrument: a pytest plugin wrapping the known-expensive primitives
(`ast.parse`, `scan_directory`, `load_registry_tree`, `yaml.load`,
`LocaleManager.get_codebase_keys`) and reporting, per primitive, total calls,
DISTINCT arguments, and therefore REPEATS. A count does not care about load, and
duplicated work -- the thing this campaign hunts -- is a count.

### Validating it first caught a flaw that would have inverted the result

Run against a gate whose answer was already known (`test_no_broad_exception_raises`,
which uses the shared session prime and should show almost no repeated parsing),
the first version reported 127 repeats concentrated in a single `<str>` bucket.

The bucket was the bug. `ast.parse(source, filename)` passes the filename
POSITIONALLY at many call sites, and the keyer read only the `filename` KEYWORD,
so every positional call collapsed into one indistinguishable bucket. The
instrument would have reported "no duplicate file parses" precisely when the
duplicates were the ones worth finding, and reported a large fake repeat count
for the collapsed bucket at the same time -- wrong in both directions at once.

Fixed to read the positional argument, the same gate reports 5274 calls, 5221
DISTINCT, 53 repeats, nearly all synthetic in-memory controls. That matches what
the shared-prime design predicts, which is what validation against a known
answer is for.

### The lesson that cost the round its finding: a repeat count is not a cost

The `dev/docs` run reported `scan_directory` at 181 calls, 54 distinct, **127
repeats** -- the legal directory walked 44 times, `docs` 36 times, the
terminology concepts 20 times. That reads like a textbook dedup target.

Measuring the unit cost dissolves it:

    legal directory        0.001s x 44 = 0.04s
    terminology concepts   0.001s x 20 = 0.02s
    docs                   0.333s x 36 = ~12s   (of a 1189s run)

The two headline repeat counts are worth forty and twenty MILLISECONDS. A
frequency-ranked instrument promotes whatever is called most often, which
correlates with cost only when the unit costs are comparable -- and here they
differ by more than two orders of magnitude. The counter answers "what repeats",
never "what costs", and the two questions have different answers.

### And the one non-trivial repeat must not be cached anyway

The `docs` walk is the only repeat with real weight (~12s, 41,217 entries). It
is also a walk over BUILD OUTPUT that the tests themselves produce. Caching it
would serve a stale listing to a test inspecting a site built after the cache was
filled -- the exact distinction `tests/_inventory` already draws between its
cached `python_files_under` and its deliberately UNCACHED `iter_files_under`.

So `dev/docs` yields no actionable duplication. Recorded as measured-and-clean
rather than unprofiled, which is the opposite of the `dev` entry above.

### Status of the instrument

Kept as a technique, not committed: it is a scratch plugin, and its output needs
a per-primitive unit cost beside the repeat count before any entry in it should
be read as a target. Without that column it ranks the cheapest thing in the tree
first.

## CRITICAL: xdist workers were dying, and the harness absorbed it silently

Profiling the `dev` slice kept failing in a way that was not a slow test. The
run wedged with no output for thirty minutes -- twice, the second time on an
otherwise IDLE box -- or ended in an xdist `INTERNALERROR`:

    KeyError: <WorkerController gw6>
      xdist/scheduler/loadscope.py:275 in _assign_work_unit
      self.registered_collections[node]

`gw6` is the tell. The repository's own hook resolves `-n auto` to six workers
(gw0-gw5), confirmed for both the `dev` and `src` paths, so a seventh
controller can only be xdist REPLACING a node that died. The replacement has no
registered collection, and the scheduler raises.

### The chain, established rather than inferred

1. `dev/docs/tests/test_sequence_goldens.py::TestCommittedGoldensCleanGate::test_every_committed_golden_matches_live_execution`
   measures **344s on an idle box** against the repository's **300s** ceiling.
2. When that ceiling fires, the test's thread is parked in `subprocess.wait()`
   on eight child interpreters. pytest-timeout falls back to the `thread`
   method on this platform, and a thread blocked in subprocess I/O is not
   interruptible.
3. So the WORKER exits uncleanly -- `[gw3] node down: Not properly terminated`
   -- rather than the test failing.
4. xdist replaces the node and re-runs the work. A bounded reproduction
   (`-n2`, one test id) reported **one test id as THREE failures in 892.65s**.
   At full width it instead wedged the scheduler.

Each step was reproduced, not reasoned: the crash was named by re-running with
`--max-worker-restart=0`, the 344s figure came from a serial run, and the
triple-report came from the bounded `-n2` reproduction.

### Why the existing guard never caught it

`timeout = 300` was added against precisely this symptom -- its comment records
"the CI unit lane sat 3-5.5h wedged with idle workers on every recent run" --
and it is the right guard for the wrong failure. It bounds a hung TEST. It
cannot bound a dead WORKER, and worse, it is what KILLS the worker: the ceiling
fires on an uninterruptible thread, so the process dies instead of the test.
Every wedge observed here happened with that setting active.

The other existing mitigation, capping `-n auto` to six workers, reduces how
often this happens without ever detecting it. Its own docstring names the
consequence -- "xdist workers crashing mid-run, which corrupts a run's own
results" -- so the failure mode was known and absorbed rather than surfaced.

### The management principle: a dead worker is terminal, never transient

`--max-worker-restart=0` is now in `addopts`. A worker death stops the session
and names the test it died on. The two shapes it replaces are both worse than
stopping: a silent retry corrupts the result set (one id, three verdicts), and
a wedged scheduler burns a runner to its lane timeout with no output at all.

Absorbing a crash is what turns one broken test into an unreliable suite. The
setting is pinned by `src/cadrumo/tests/test_xdist_worker_lifecycle_policy.py`,
which matches the FLAG rather than the option name -- `--max-worker-restart=2`
is the tolerant setting the gate exists to reject and would satisfy a name-only
check -- and was proven to red by rebinding its config reader from outside the
repository, so no tracked file was mutated to prove it.

Alongside it, the two gates that fan out into an 8-wide child pool now carry
their own generous ceilings, so the default stops firing mid-wait.

### The policy paid for itself immediately

The first full `dev` run after the change COMPLETED -- 985s, with a durations
table, where the same command had twice produced nothing at all. The
sequence-goldens gate now appears in that table as an ordinary 97.74s entry.

It also named a SECOND test of the same class, which the silent-restart
behaviour had been hiding:
`dev/packaging/tests/test_release_cohort_integration.py::test_real_clean_source_build_is_complete_and_reproducible`,
which clones the source and builds the twelve-member cohort twice in child
processes. It has been given its own ceiling too.

That is the argument for failing loudly, made by the change itself: the defect
had been in the tree long enough to be normalised, and one run of an
intolerant harness found it.

### Standing shape

Default 300s ceiling for ordinary tests, which never approach it; explicit
generous ceilings on the handful of gates that legitimately outrun it in child
processes; and a fail-closed backstop that names any future offender instead of
absorbing it. The backstop is what makes the exception list maintainable -- a
new heavy test announces itself once, loudly, rather than degrading the suite.

## Round: the dev durations table, finally readable

The fail-closed worker policy above is what made this round possible: the `dev`
slice had never produced a durations table, because every attempt wedged. The
first run after the fix completed in 985s and ranked, for the first time:

    177.91s  packaging test_core_wheel_contains_every_runtime_member_and_no_split_owned_binary
    109.03s  packaging test_real_wheels_form_one_complete_authority_cohort
     97.74s  docs      test_every_committed_golden_matches_live_execution
     96.78s  docs      test_every_enrolled_page_is_coherent_top_to_bottom
     95.34s  packaging test_three_wheel_cohort_installs_only_aeat_human_script

### Fixed: the three-wheel cohort was built twice

The second and third entries live in one module and built the IDENTICAL cohort
from the IDENTICAL `build_root`, differing only in the directory it landed in.
Measured directly rather than inferred from the durations: `build_wheel` 16.5s
plus `build_companion_wheels` 38.8s, so each test spent ~55s reproducing the
other's artifacts.

A module-scoped fixture now builds once. The run shows exactly the intended
shape -- ONE 54.63s setup where there were two builds -- and the module falls
from the 204.37s the two tests summed to, to 152.97s.

Safe because the wheels are consumed READ-ONLY: opened with `zipfile`, and
handed to pip as resolved absolute paths. Everything a test mutates -- its
venv, its install, its product state -- still comes from that test's own
`tmp_path`, so the tests stay independent in every respect except the bytes
they read. `_install_cohort_with_pip` takes the work directory only as a `cwd`,
which was checked before relying on it.

The first entry (`test_core_wheel_contains_every_runtime_member_and_no_split_owned_binary`,
177.91s) is NOT part of this: it builds from `commit_defined_build_root`, a
clean commit-defined extract, so its artifacts are genuinely different and
cannot be served from the same fixture.

### A limit of the snapshot technique, worth recording

The usual before/after -- `git archive` a commit into scratch and run both
trees -- CANNOT be used on this module. The build shells out to `git ls-files`,
and an archived tree has no `.git`, so the baseline run failed instantly with
`command failed (128): git ls-files src/cadrumo/_data` rather than producing a
figure.

That failure was loud, so it did not become a fake baseline. But a quieter
variant of the same thing would: a snapshot that runs but silently takes a
different path than the live tree measures something other than what it claims.
Where the technique cannot apply, the component measurement (the 16.5s and
38.8s builds, taken directly) is the honest substitute -- not a snapshot figure
obtained by working around the obstacle.

Deliberately NOT worked around by reverting the tracked file in place to
measure it: a mutation window in this worktree is shippable state, and peers
commit continuously.

### The remaining failure is not this change

`test_real_wheels_form_one_complete_authority_cohort` fails on
`authority.validate_registry()` raising a pydantic `ModeloRevision` pattern
mismatch -- the standing tree-wide registry red, now reaching the packaging
probe. This change alters WHERE wheels are built and never their content, so it
cannot produce a registry validation error. Checked by reading the actual
exception rather than accepting the pass/fail count.

## Round: four dev targets ruled out, and a correction to how the table is read

No change this round. Every remaining dev target above ~40s was investigated
and each is either irreducible, protected, or was never as expensive as the
table said.

### `-n auto` durations rank work PLUS contention

`test_checked_rehoming_ledger_is_an_exact_live_source_join` sat at 45.57s in the
table. Its components, measured in isolation, are
`current_source_fingerprints` 10.5s (called ONCE),
`load_rehoming_ledger` 0.6s x 6, and `_historical_non_null_identities` 0.6s --
about 12s of work. Run alone it takes **12.94s**.

So the durations entry was ~3.5x its own work; the rest was time spent competing
with five sibling workers. That is not a flaw in pytest -- wall clock is wall
clock -- but it is a flaw in reading the table as a work ranking.

The consequence for this campaign: a mid-table `-n auto` entry must be
re-measured in isolation BEFORE it is treated as a target, or the "optimisation"
chases waiting rather than working. The top entries here survive that test
because they are subprocess-bound builds whose cost is real, but nothing below
them should be trusted on the table alone. Every earlier win in this document
was verified by isolated or component measurement, so none of them rests on this
mistake -- but only by habit, not because the hazard was understood.

### Ruled out, with the measurement

**`test_core_wheel_contains_every_runtime_member_and_no_split_owned_binary`
(177.91s).** One test performing three genuine builds -- wheel, companions and
sdist -- from `commit_defined_build_root`, a clean commit-defined extract. The
module's only other test exercises `commit_defined_build_root` against tiny
synthetic repositories and is cheap. Its build root DIFFERS from the
split-install module's (`_REPO_ROOT`), so its artifacts cannot be served from
the fixture added there. Nothing is duplicated; the cost is three builds it is
the point of the test to perform.

**`test_live_fixture_ownership_manifest_is_complete_and_has_no_substitutable_duplicate`
(47.39s).** `census(REPO_ROOT)` measures 37.16s and 39.12s on consecutive calls
-- uncached -- over 5651 files. But `check_manifest` calls it exactly ONCE, so
there is nothing to share.

More importantly, memoising `census` would be actively wrong. `stable_manifest`
and `stable_census` snapshot the source universe BEFORE and AFTER the scan and
refuse a tree that moved during it. A cached census returns a result computed at
some earlier moment while the guard compares two fresh snapshots around what has
become a no-op -- the guard would still pass, having watched nothing. This is
the third instance of the same shape in this campaign, after the drift census
and the tax-id determinism pair.

**`test_no_reviewed_acceptance_is_reported_as_a_failing_hotspot` (42.92s).** One
`audit_complexity()` call. Its other caller lives in a different module, and
under `--dist=loadfile` different modules land on different workers, so there is
no shared process to memoise into. Cross-module sharing here would pay off only
when the scheduler happened to co-locate them.

## A completed run destroyed at teardown by the SHARED pytest temp root

The package-local slice (`src/cadrumo` minus `src/cadrumo/tests`, ~24k tests)
ran to **100%** with **zero worker deaths** -- the fail-closed policy from the
previous round held across the whole slice -- and then lost its entire report:

    File "_pytest/pathlib.py", line 371, in cleanup_numbered_dir
      cleanup_dead_symlinks(root)
    File "_pytest/pathlib.py", line 356, in cleanup_dead_symlinks
      if not left_dir.resolve().exists():
    PermissionError: [WinError 5] Access is denied:
      'C:\Users\hello\AppData\Local\Temp\pytest-of-hello\pytest-current'

Every test had executed. The durations table and the pass/fail summary were
never printed, because the exception escaped the session finalizer. Roughly
eighty minutes of work produced no readable result.

### Why it happens here specifically

`pytest-of-hello` is a per-USER temp root, not a per-session one, and several
pytest sessions run concurrently on this box at all times. At teardown pytest
walks that shared root and stats `pytest-current`, a symlink each session
replaces as it starts. When a peer session swaps it mid-stat, Windows answers
Access Denied rather than "missing", and the reaper raises instead of skipping.

This is the same FAMILY as the xdist worker death fixed above: not a test
failing, but the harness's own lifecycle handling discarding a run that had
already succeeded. The failure lands at the last possible moment, which is what
makes it expensive -- the cost is the whole run, every time.

The repository already reasons about this concurrency at the OTHER end. Its
numbered-dir reaper exists precisely because "several sessions may run
concurrently ... each of them runs this reaper at its own startup", and it is
careful to spare a running session's directory. Startup is owned and guarded;
teardown is still pytest's own and unguarded.

### Not fixed here, deliberately

The teardown path is inside `_pytest.pathlib`, reached through a session
finalizer. Making it tolerant means either patching a private pytest internal
from `conftest.py`, or moving every session to a private `--basetemp` -- which
would sidestep the collision but also opt out of the numbered-dir retention that
keeps this box's temp from filling (39.1 GB was measured once, and is why the
retention policy exists). Both are harness-lifecycle decisions with a blast
radius beyond this campaign, and the second trades one disk hazard for another.

Recorded with the reproduction so the choice is made deliberately rather than
under time pressure mid-profile. Profiling runs in this campaign now pass an
explicit private `--basetemp`, which is safe for a throwaway run precisely
because nothing needs to retain its directories.

## The largest lever in the campaign: KDF calibration re-measured per registration

Profiling the slowest package-local test
(`test_profile_selection_precedence_uses_explicit_flag_then_pointer`, 134.53s in
the table and **127.29s in isolation**, so real work rather than contention)
found the cost was not where the test looks. A cProfile of one profile
registration:

    19.14s  _register_profile
    16.92s    register_profile_with_credentials
    16.56s      create_profile_custody_registration_material
    16.11s        calibrate_profile_kdf        <- 14 x _measure_profile_kdf

`calibrate_profile_kdf` MEASURES the parameter grid on the host -- one
supervised child process per warmup and per sample -- to pick the strongest KDF
point inside the operator latency band. It then does it again for the next
registration, on the same machine, for the same answer.

### The repository had already written the escape, and the reasoning

The seam exists: `cadrumo_profile_kdf_measure_calibration`. Its own comment
inside `calibrate_profile_kdf` states the case exactly -- measuring is "the
right price for an operator's one-off enrolment and the wrong one for a host
that enrols constantly" -- and records that declining to measure adopts the
SAME fixed point the function returns when the grid cannot be measured before
its deadline, "a stronger point than the measured band's floor, so nothing
about the wrap weakens".

`src/cadrumo/tests/secure_sql.py` already takes that seam in three places. The
shared CLI registration door, `register_cli_profile`, did not -- and it has
**156 call sites across 62 modules**. The lever was not a new idea; it was an
existing, documented, already-used decision that one door had missed.

    one registration : 17.44s / 17.61s  ->  2.20s / 1.41s
    custody module   : 239.79s          ->  155.81s

with IDENTICAL failure sets by name (3 failed, 3 passed on both sides).

### Why this is not a security weakening, checked rather than argued

Three things were established before the change, not after:

- The fallback is the same fixed point calibration itself falls back to on
  deadline, and stronger than the measured band's floor. That is the shipped
  function's own claim about its own fallback, not an assumption about it.
- The calibration BEHAVIOUR is proven by
  `custody/tests/test_kdf_supervision.py`, which drives `calibrate_profile_kdf`
  directly and was confirmed never to reach it through this door. So no
  calibration regression can hide behind the change; that gate still passes
  17/17 after it.
- Only the TEST door changed. The production path, and any test that wants real
  measurement, is untouched.

The count of 156 call sites is deliberately NOT reported as a time saving. It is
a count, and this campaign has already recorded what happens when a repeat count
is read as a cost. What is measured is the per-registration figure and one
module; the suite-wide effect follows from those two, and will be visible in the
next full profile rather than asserted here.

## Round: the package-local ranking after the KDF fix

Re-measuring the remaining package-local targets in isolation, per the method
rule, shows the KDF calibration fix already collected most of them:

    in-table (-n auto)   isolated (after)
    99.75s          ->   22.76s   test_batch_transform_recategorize_relabel_reallocate_at_scale
    48.50s          ->   29.63s   test_cold_process_m100_2025_work_create_keeps_intracom_type_import_boundary
    47.21s          ->   30.75s   test_cold_process_work_create_registers_wizard_catalogue

The ~17s that came off each cold-start test is one KDF calibration, which is the
expected shape: each registers a profile in-process before handing the storage
root to a cold child. The batch-transform figure moves further because it was
also carrying contention, exactly the inflation the method rule exists to catch.

None of these needs separate work. What remains in them is subprocess CLI boots
and the work they exist to exercise.

### Ruled out: `test_every_bundled_design_produces_a_classified_outcome`

The one target in this ranking that is NOT contention: 55.27s in-table and
**59.51s in isolation**, so if anything the table understated it.

`_outcomes()` is called by four tests in the module and carries no memo of its
own, which reads as textbook duplication. It is not. Measured directly:

    _outcomes call 0: 58.65s   (218 designs)
    _outcomes call 1:  0.06s
    _outcomes call 2:  0.06s

Something downstream of `_classify` already memoises per design, so the first
caller pays and the other three are free -- which is why the module totals
60.30s with one test at 59.51s rather than four times that. The remaining cost
is a single pass over 218 bundled designs at roughly 0.27s each, which is the
parsing the gate exists to perform.

Worth stating as a pattern: an uncached-looking helper called from four tests is
not evidence of four executions. The module total is the cheap check that
distinguishes them -- four uncached calls here would have produced a ~240s
module, and it produced 60.30s.

## Round: the KDF lever, followed across the process boundary

The full `src/cadrumo` profile now completes cleanly -- 33:35, no worker
deaths, durations printed -- which the fail-closed worker policy and an explicit
private `--basetemp` together made possible. It surfaced a module the earlier
rankings never reached, and following it exposed that the previous round's fix
was only half the lever.

### A session default cannot cross a spawn boundary

`register_cli_profile` was fixed last round, but 102 further call sites across
31 test modules reach `register_profile_with_credentials` DIRECTLY. A
session-scoped autouse `override_settings` in `cadrumo/conftest.py` now covers
those, and three properties were checked before adopting something that broad:

- `override_settings` does NOT reach a directly-constructed `Settings`
  (`load_settings()` reads False under it while `Settings()` still reads True),
  so the calibration gate, which builds its own, is out of reach.
- A NESTED `override_settings` setting other fields preserves this value, so
  the many tests that override a storage root do not silently re-enable
  measurement.
- No test outside the gate asserts a measured calibration source. The
  `"measured"` hits elsewhere are `identity_measurement` in registry
  conformance -- an unrelated concept, checked rather than pattern-matched.

It then did not work on the module that surfaced it: 48.54s in the table,
46.90s isolated, and **46.90s still** with the session default in place.

The reason is worth recording as a general limit. Those registrations run in
processes started with `get_context("spawn")`. A spawned child re-imports and
rebuilds its configuration from scratch, so no in-process context manager
survives into it. And the shared `_child_settings` helper passes
`_env_file=None`, so an environment-variable default -- the usual way to reach a
child -- would not have worked either, and would additionally have broken the
calibration gate, whose `Settings(...)` DOES read the environment.

The only thing that reaches such a child is an explicit constructor argument,
which is what `_child_settings` now passes.

    that test          : 46.90s -> 15.50s
    the two modules
    sharing the helper : 292.47s -> 175.68s

with IDENTICAL failure sets by name (10 failed, 23 passed on both sides), and
the calibration gate still 17/17.

### The shape to carry forward

One lever, three distinct doors: a shared test helper, a session default for
direct in-process callers, and an explicit argument for spawned children. Each
was invisible from the others -- the first fix looked complete, and only
measuring a module that still had not moved showed it was not. A cascade that
stops at a process boundary looks exactly like a cascade that finished.

## Ruled out: the cold-start CLI children do NOT calibrate

The previous round ended by suspecting the cold-start CLI tests: they spawn real
`aeat` subprocesses, and the spawn boundary had just been shown to defeat both
the session default and any environment default. Two of them still cost ~30s
each, which fit the shape of one unfixed calibration.

They do not calibrate. `calibrate_profile_kdf` is reached only from
`create_profile_custody_registration_material` -- at REGISTRATION -- and these
children log in and run work commands against a profile the PARENT registered
in-process. The child's cost is CLI boot and the work itself.

Settled by experiment rather than by reading the call graph, because the call
graph is what produced the wrong hypothesis in the first place. The setting was
added to the child's environment dict and the module re-run, same box, back to
back:

    work_create_registers_wizard_catalogue     30.05s -> 30.81s
    m100_2025_work_create_keeps_intracom...    29.29s -> 29.85s

No effect beyond noise, so the hypothesis is dead and the setting was removed.

### The probe was swept into HEAD before it could be judged

The experiment ran for about a minute; a concurrent sweep committed it during
that window, under a subject asserting the benefit the measurement was about to
disprove. It has been removed with a commit that says so.

Recorded because it is a hazard this campaign has been navigating all along and
this is the first time it caught an EXPERIMENT rather than finished work. A
speculative edit in this worktree is publishable state from the moment it
touches disk. The lesson is not "stop probing" -- the probe was the right move
and cheaply killed a plausible wrong idea -- it is that a probe must be measured
and then reverted or committed deliberately in one go, never left resident while
a run finishes.

A disproven setting is also worth removing rather than keeping as
belt-and-braces: kept, it reads as a tuned knob and the next reader inherits the
hypothesis rather than the measurement.

## Round: three more targets ruled out, all by the same discriminator

No change this round. Each remaining target from the clean full profile was
re-measured in isolation first, then probed with the repeat-cost check that has
now settled several of these.

**`test_a_design_title_never_contradicts_a_trustworthy_filename_year`** --
58.31s in-table, **55.90s isolated**, so genuine work. It reads every bundled
design's title, and three sibling tests in the module read designs too, which
looks like a shared-fixture opportunity. Measured instead:

    full pass over 218 designs, call 0 : 72.89s
    call 1                             :  0.00s

Already memoised downstream. The first test pays and the siblings do not repeat
it, so there is nothing to share. One genuine pass over 218 PDFs and workbooks.

**`test_family9_has_no_orphaned_reexport_bridges`** -- 46.86s in-table, 38.47s
isolated. Its module IMPORTS `_package_import_sites` and `_package_py_files`
from `test_import_hygiene_gate`, i.e. the cached helpers added earlier in this
campaign, so the tree walk is already shared across both modules. Its own
components measure `find_shim_modules` 5.54s (once) and
`first_party_census_files` 0.19s; the remaining ~33s is the single orphan scan
the test exists to perform.

**`test_bootstrap_safe_probes_still_run_on_root_fallback_database`** -- 42.69s
in-table, 37.17s isolated. The module declares no fixtures at all: every test
calls `run_cadrumo_subprocess` directly, and the cost is real CLI process boots.
A guard against a root-fallback database cannot be exercised in-process, so the
subprocess IS the test.

### The discriminator that keeps working

Three targets, three plausible duplication stories, three refutations from the
same two-line check: call the suspected shared computation twice and time both.
A second call at 0.00s means the work is already shared however the code looks;
a second call at full cost means it is not.

That check has now been decisive five times in this campaign, twice against my
own strong prior. It is cheaper than reading the call graph and, on the evidence
here, more reliable -- the call graph is what produced the wrong hypothesis in
the cold-start round.

### A quiet confirmation worth noting

`test_import_edge_integrity_gate` importing the cached helpers from
`test_import_hygiene_gate` means an earlier fix in this campaign is being reused
by a module it was not written for. That is the shape worth preferring: the win
compounds where a per-module fixture would not have.

## Round: the last two targets, and confirmation the KDF fix cascaded

**`test_enrollment_wraps_the_profiles_own_key_under_a_minted_mnemonic`** was
33.35s of SETUP in the full profile. Isolated now: **1.85s setup, 8.76s for the
whole module of 16 tests**. Nothing was done to this module. It registers
profiles, so the KDF change collected it.

That is the confirmation the previous rounds could only predict. The KDF lever
was measured on the doors it was applied to; this is a module nobody touched,
carrying an 18x drop, which is what a cascade looks like from the outside. It
also re-validates the reading rule: a large SETUP figure is a bill, and this
bill was being paid by a calibration that no longer runs.

**`test_pdf_corpus_text_sidecars_equal_current_production_extraction`** --
33.87s in-table, **32.25s isolated**, so genuine work with no contention
inflation. It re-extracts text from every PDF in the corpus and compares against
the committed sidecars. It is the only PDF-extracting test in its module (the
siblings cover HTML normatives at 4.02s and source matching at 1.37s), so there
is no second caller to share with. The cost IS the extraction the gate exists to
verify.

### State of the durations-driven phase

Every entry above ~30s isolated, across all three slices, has now been examined.
The tally for this phase:

- FIXED where work was genuinely duplicated: KDF calibration (three doors),
  locale catalogue parsing, import-hygiene scanning, IVA stem passes, the audit
  shadowing dimension, the drift census, the packaging cohort build, the
  registry accessor migration, `get_codebase_keys`.
- RULED OUT with a measurement, and recorded so they are not re-chased: fifteen
  or so targets whose cost is either already shared downstream, irreducible work
  the gate exists to perform, or an oracle whose duplication IS the measurement.

The ratio has inverted. Early rounds found duplication in most targets; the last
four rounds produced one fix and eleven rule-outs. That is the signal that this
phase is done rather than merely slow: the remaining cost in this suite is work
the tests are for.

Two items with real headroom remain, both recorded above and both requiring an
owner's decision rather than more profiling: the nineteen production
`load_registry_tree` sites, and the teardown `PermissionError` that destroys a
completed run's entire report.

## The cascade is real per-test and nearly invisible in suite wall clock

A fresh full `src/cadrumo` profile, taken to measure the KDF work at suite
scale:

    before (fix 1 only) : 2015.64s
    after  (all 3 doors): 1923.11s

**-4.6%**, and that figure is NOT claimed as the result. The two runs differ in
test population (22732 vs 22700 passed, 5210 vs 5242 failed) because peers
committed throughout, so a 4.6% move is inside what tree drift and contention
alone could produce.

This sits against per-test evidence that is not marginal at all:
`test_recovery_custody` setup 33.35s to 1.85s, the registration modules 292.47s
to 175.68s, one registration 17.5s to 2s. Those were measured back to back with
identical failure sets.

### Why both readings are true

Under `-n auto --dist=loadfile` with six workers, suite wall clock is the
longest WORKER's chain, not the sum of the work. The KDF fix removed a large
amount of CPU spread thinly across many profile-registering tests -- and almost
none of it from the files that define the critical path, which are the ones at
the top of the ranking and which mostly do not register profiles at all:

    116.24s  test_acceptance_wall_catalogue (setup)
    103.93s  test_config_custody_profile_lifecycle
     99.19s  test_ledger_corpus_batch_transform
     78.29s  test_wheel_content_boundary (setup)
     77.19s  test_dev_audit_report (setup)

So the suite got materially cheaper in CPU and barely faster in wall clock.

### What this changes about targeting

The loop has been picking the slowest individual TESTS. For suite wall clock
under `loadfile`, the unit that matters is the slowest FILE, because a file is
what gets assigned to a worker. Optimising a slow test inside a short file
returns CPU and developer patience; it returns wall clock only when that file
was on the critical path.

Both are worth having -- CPU is what a shared, contended box actually runs out
of, and this campaign has spent most of its time waiting behind peers -- but
they are different objectives and should not be reported as one. Everything
above is per-test evidence and stands; no suite-level wall-clock claim is made
for any of it.

The ranking itself is essentially unchanged from the previous profile, which
independently confirms the phase conclusion: the remaining top entries are the
ones already examined and ruled out as irreducible or already shared.

## The suite is CPU-bound, not tail-bound -- which retires the "slowest file" idea too

The previous entry concluded that suite wall clock is set by the longest FILE
under `--dist=loadfile`, and that per-test work therefore buys CPU rather than
wall clock. The first half of that is wrong, and it was wrong because it was
reasoned rather than measured.

Measured properly, by running with `--durations=0` and aggregating the 23,922
recorded phases per FILE -- an instrument this campaign had not used before:

    total recorded CPU     : 9,354s
    suite wall clock       : 1,843.55s across 6 workers
    perfect-balance floor  : 1,559s   (9,354 / 6)
    longest single FILE    :   169s
    worker utilisation     :   85%

The suite runs 18% above a perfect-balance floor, and the longest file is 169s
against a floor of 1,559s. **No file is anywhere near the critical path.** There
is no tail to cut: the binding constraint is total CPU divided by workers.

The top twelve files together are 1,238s, or **13.2%** of all recorded CPU. So
deleting the twelve slowest files outright -- every one of them a gate this
campaign has already examined and mostly found irreducible -- would cut wall
clock by at most about 13%.

### What actually moves this suite

Only two things:

1. **Broad, cross-cutting CPU reductions.** A change that touches one test
     removes at most ~1% of one file; a change that touches a category of tests
     removes real CPU. The KDF calibration fix is the shape that works, and its
     modest 4.6% wall-clock effect is now explicable rather than disappointing:
     it removed a few hundred seconds from 9,354.
2. **More workers.** At 85% utilisation the schedule is already good, so wall
     clock tracks `CPU / workers` closely. This is a policy knob
     (`DEFAULT_WORKER_COUNT` is 6 on a 24-core box, deliberately leaving room
     for co-resident agents), and it is coupled to the 1,216 MB-per-worker AST
     prime, so it is an owner's decision and not a performance finding.

### Two reasoned conclusions, both corrected by one measurement

This campaign has now had to correct its own targeting twice, and both times the
fix was a measurement it had not thought to take:

- "`-n auto` durations rank work" -- false; they rank work PLUS contention,
  caught by re-measuring a 45.57s entry at 12.94s in isolation.
- "wall clock is set by the longest file" -- false; no file is remotely large
  enough, caught by aggregating per file instead of reading the top-N test list.

The common failure is reading a RANKING as if it were a model of where time
goes. `--durations=N` answers "which tests are slowest", which is not "what is
the suite waiting on", and neither question was the one that mattered. The
per-file aggregation cost one extra flag on a run that was happening anyway.

## Where the 9,351s actually lives

With per-test targeting exhausted and the suite shown to be CPU-bound, the
useful question became which CATEGORY carries the mass. Aggregating a
`--durations=0` run three ways:

    by phase      call 7,619s (81.5%)   setup 1,625s (17.4%)   teardown 108s (1.2%)

    by package    3,356s  35.9%  src/cadrumo/entrypoints/cli
                    962s  10.3%  src/cadrumo/domain/calculations
                    566s   6.1%  src/cadrumo/application/modelo
                    374s   4.0%  src/cadrumo/application/user_profile
                    317s   3.4%  src/cadrumo/application/ledger

    concentration top  10 files 11.7%   top 100 files 51.2%
                  top 250 files 72.8%   top 500 files 87.6%
                  files under 1s each: 237s = 2.5%

Three things follow that no ranking showed.

**The CLI suite is the only category with real mass** -- 35.9%, more than three
times the next. Any future broad lever is there or nowhere.

**It is not a long-tail problem.** Half the CPU is in 100 files out of 2,326,
and everything under one second put together is 2.5%. Sweeping small tests would
be busywork.

**Setup is 17.4%.** That is the fixture surface this campaign has been sharing,
and it is now a sixth of the total -- worth knowing before anyone assumes more
fixture sharing is where the remaining time is.

### What is NOT established, and the measurement that would settle it

The obvious story is that the CLI mass is subprocess boots. The per-boot floor
was measured -- a cold `aeat --help` child costs 0.70s warm, 1.38s first -- and
the CLI import it pays is 0.769s once per process, not per test.

That is a floor, not an attribution. Reaching 3,356s from 0.70s boots needs
roughly four thousand of them, and the actual spawn count across the CLI suite
has NOT been measured; the static count is 119 `subprocess.run` sites over 76
files, which says nothing about executions. Real commands also do far more than
`--help`: registry loads, profile unlocks, ledger work.

So the CLI mass is recorded as UNATTRIBUTED. Settling it needs an aggregated
spawn count across that suite, which requires either a single-process run of the
CLI slice (~56 minutes at its measured CPU) or a per-worker counter that
aggregates in the xdist controller, which the scratch counter does not do.

Written down explicitly because this campaign has twice shipped a conclusion
that was reasoned rather than measured, and "it must be the subprocesses" is
exactly the shape of both.

### Process note: do not delete the log before the analysis is finished

Two of this round's three profile runs were re-runs, because the log was deleted
immediately after extracting the one number that had been planned for. Each
re-run cost half an hour of wall clock for data that had already existed. The
log is a few tens of kilobytes with `--tb=no`; the analysis is cheap and
iterative and the collection is not.

## The CLI mass, attributed: subprocesses are 28% of it, not the story

The previous entry recorded the CLI suite's 3,356s as UNATTRIBUTED and named the
measurement that would settle it. Taken:

    CLI test time (all workers) : 2,921s
    time inside spawned children:   824s   = 28.2% of CLI test time
    spawns                      : 2,541 outermost, mean 0.32s each
    in-process CLI work         : ~2,097s = the other 71.8%

Against the whole suite's 9,351s, subprocess time is **8.8%**. So eliminating
every spawn in the CLI suite -- which is impossible, since they exist to prove
cold-process behaviour -- would return under a tenth of the suite's CPU.

The hypothesis was directionally right and quantitatively wrong, which is
exactly why it was recorded as unattributed rather than acted on. The real mass
is the CLI's IN-PROCESS work: roughly 2,097s, about 22% of the entire suite, and
2.5x the spawn time.

Note also the mean spawn is 0.32s, BELOW the 0.70s `--help` floor measured
earlier. A floor measured on one command is not the mean of a population of
commands, and reasoning "at least 0.70s each x N spawns" would have overstated
the total by more than double.

### The instrument was wrong twice before it was right

Worth recording, because the errors were opposite and both plausible:

- Timing `subprocess.run` AND `Popen.wait` charged the same seconds twice:
  63.66s against a 67.50s module.
- Timing only `Popen.wait` reported 0.099s, because `subprocess.run` blocks in
  `Popen.communicate()` and reaches `wait` after the child has already exited.

The fix times only the OUTERMOST spawn, via a re-entrancy depth counter, and
wraps `communicate` as well. Validated at 63.08s of 66.69s (94.6%) on a module
already known to be subprocess-bound -- a known answer chosen precisely because
a wrong instrument would be visible against it.

Both errors would have produced a confident number. The first would have said
subprocesses are ~94% of CLI time and sent the next round chasing them; the
second would have said they are ~0% and retired them. The measured answer, 28%,
is between the two lies and matches neither.

### What this leaves

A precise next question rather than a lever: what does the CLI suite's ~2,097s
of IN-PROCESS work consist of? That is the largest single identified block of
CPU in the suite. It is NOT claimed here to be shared or reducible -- this
campaign has learned what happens to unmeasured claims -- only that it is now
located.

## The CLI's in-process mass is real work, and its one duplication is deliberate

Profiling the largest in-process CLI module (`test_ledger_list_filter.py`, 155s)
under cProfile, first-party frames by cumulative time:

    148.4s  n=67   tests/cli_runner.py:invoke_cached_cli
     89.3s  n=10   test_ledger_list_filter.py:_import_corpus
     82.5s  n=40   _ledger_import_cli.py:ledger_import
     63.3s  n=40   application/ledger/_actions_import.py:import_ledger_transactions
     46.1s  n=111  adapters/persistence/profile/transactions.py:load

Two findings, and both close the line of investigation rather than opening one.

**The framework overhead is already cached.** `invoke_cached_cli` averages 2.2s
across 67 invocations, but that figure is the COMMANDS, not the harness: the
Click command tree is built once behind `@cache`, and `cadrumo_click_command`
says why in its own docstring -- Typer rebuilds the full tree per invocation and
"repeated materialization dominates test runtime". Somebody took this lever
already, for the reason I would have taken it. What remains inside those 2.2s is
ledger imports at ~1.6s per file, listings, and encrypted stores doing their
work.

**The one real duplication is protected.** Nine of the module's tests each call
`_import_corpus()`, importing the same four CSVs through the real CLI at ~8.9s
apiece -- 89.3s of a 155s module, and every one of those tests is read-only
afterwards (no mutating verb appears anywhere in the file). That is precisely
the shape that worked for the packaging cohort.

It is not available here. Isolation comes from `live_fx_isolated_backend`, which
is `autouse=True` and FUNCTION-scoped, and is used by fourteen modules. Sharing
one imported corpus across the nine tests means giving them a shared backend,
which is exactly the per-test isolation that fixture exists to provide -- and
which the sibling `_evict_test_bound_bucket_session` guard exists to reinforce,
after an unsealed session was observed crossing between tests and decrypting
against the wrong bucket's DEK.

So this would trade a real correctness property, in fourteen modules, for ~80s
in one. Declined, and recorded here so the 89.3s is not rediscovered later as an
unexplained opportunity: it is explained, and the explanation is that isolation
costs what it costs.

### Where this leaves the CPU question

The suite's largest identified block -- the CLI's ~2,097s of in-process work --
is commands executing against encrypted per-test stores. The harness overhead
around it is already memoised, and the repeated work inside it is repeated
because each test insists on its own world. There is no broad lever here of the
kind the KDF calibration was.

## A whole testpaths entry had never been profiled

`pyproject.toml` lists three `testpaths`: `src/cadrumo`,
`src/cadrumo-harness`, and one packaging file. Every profile in this campaign
ran against `src/cadrumo`. The harness package -- 54 test files, 400 tests --
had never been measured at all, and the "all slices profiled" conclusion
recorded above was therefore wrong about its own coverage.

It was found by re-reading the configuration rather than by any measurement,
which is the uncomfortable part: eleven rounds of profiling had taken the slice
list as given instead of deriving it from what the suite actually declares.

### The lever it contained

    build_tool_descriptors : 107.3s across 14 calls, of a 144s module
      _output_schema_for   : 102.2s across 3,990 calls

One build renders ~285 output schemas at 7.7s, and the MCP tests were paying it
once per test for an answer that cannot change: the descriptor set is a pure
function of the loaded command tree, and manifest, registry and CLI argument
vectors are all fixed at import.

Two properties were checked BEFORE memoising, because this is production code
and not a test helper:

- `McpToolDescriptor` carries the strict FROZEN config, so one caller cannot
  mutate what the next receives -- safe by construction, the same reasoning that
  made the shared registry tree safe.
- The descriptions are deliberately English, not localised (the builder says so
  in its own comment), so a cached value cannot pin a locale. A localised
  description would have made this memo a correctness bug rather than a win.

And no test mutates the surface then rebuilds; every `SCHEMA_REGISTRY` use in
the harness tests is a read.

    one build            : 4.45s then 0.00s
    test_meta_tools      : 68.20s -> 33.42s
    whole harness slice  : 142.92s -> 92.84s

with identical results either side (26 failed, 374 passed). The win is not only
in tests: `_server.py` builds descriptors at startup and `_hitl.py` calls the
builder once per query.

### The lesson

The campaign concluded twice that the optimisation space was exhausted. Both
times that conclusion was true of the slices it had profiled and false of the
suite, because the slice list came from habit. A coverage claim should be
derived from the configuration that defines the population -- here, three lines
of `testpaths` -- not from the set of runs that happen to have been done.

## The harness slice, characterised -- and a production cold-start cost

The third `testpaths` entry (`dev/packaging/tests/test_installed_oracles.py`)
was checked and is already optimal: 244.35s for six tests, of which a 199.30s
`installed_cohort` fixture is MODULE-scoped, so the build-and-install is already
shared. Nothing to collapse.

The harness slice was then characterised with the spawn timer rather than
investigated test by test:

    test time (all workers) : 310s
    inside spawned children : 122s = 39.3%
    spawns                  : 20, mean 6.09s each

Twenty spawns carrying 122s. The tests that own them
(`test_inprocess_envelope_parity` and friends) run one verb through BOTH a real
`aeat` subprocess AND the warm in-process runtime, because cross-transport
parity is the claim; the duplication is the oracle, the same shape already
recorded for the TUI migration manifest. Not reducible.

### Why a spawn costs six seconds

Measured directly in a cold interpreter, twice:

    import cadrumo_harness.mcp._tools : 2.56s / 2.59s
    first build_tool_descriptors()    : 4.44s / 4.49s
    total to 285 descriptors          : 7.00s / 7.07s

So an MCP server needs about seven seconds from process start before it can
advertise its tools, and `_server.py` builds descriptors at startup. That is
user-facing latency, not a test artefact -- the tests merely pay it twenty
times.

The memo added this round does NOT reach it, and for the reason already
recorded once in this campaign: a process-level cache cannot cross a spawn
boundary. That is now the third instance of the same family (the KDF session
default, the `_child_settings` constructor argument, and this), which makes it a
reliable thing to check rather than a surprise: any in-process memo leaves child
processes paying full price, and any measurement that still shows the old cost
after a memo should be tested for a process boundary before the memo is doubted.

### Not acted on

Making MCP startup cheaper means persisting the descriptor set and keying it to
something that invalidates correctly across a version or command-tree change.
Serving a stale tool schema to a client is a correctness failure, not a slow
start, so that is a design with a blast radius rather than a memo. Recorded with
the measurement for an owner, alongside the production `load_registry_tree`
sites.

## Ruled out: deferring the harness MCP import chain

The 7.0s MCP cold start is 2.56s import plus 4.44s descriptor build. The import
half looked like the classic stray-eager-import win, and `-X importtime` named a
culprit immediately:

    2.61s  cadrumo_harness.mcp._tools
    1.94s    -> _identity_gate -> _harness_tools -> cadrumo.application.wizard

`cadrumo.application.wizard` was imported at module level in `_harness_tools`
for ONE symbol used in ONE function body. Deferring it into that body is the
pattern the file already uses for `resolve_cli_precondition_action`, and the
architecture rule explicitly permits it -- lazy resolution governs WHEN a module
executes, never WHERE a symbol lives.

It buys nothing: **2.61s to 2.58s**, inside noise. Reverted.

The reason is structural and worth recording so nobody re-attempts it.
`_harness_tools` also imports `cadrumo.application.workflow` for
`ProfileHealthStatus`, and that symbol is a PYDANTIC FIELD ANNOTATION
(`readiness: ProfileHealthStatus`). Pydantic needs the real type at
class-definition time, so that import cannot be deferred at all -- and
`application.workflow` is 1.64s of the 2.58s on its own. Wizard was merely
reaching workflow first; removing wizard from the path just exposed workflow as
the direct cost.

So the harness import cost is pinned by a model definition, not by a careless
import. Shifting it would mean relocating `ProfileHealthStatus` to a leaf
module, which is a domain-layout decision, not a performance edit.

### Two mistakes made here, both caught by measuring

The deferral was added while the module-level import was still in place, so
`ruff --fix` removed the redundant FUNCTION-LOCAL one and kept the eager one --
the opposite of the intent, and the change silently undid itself. The import
time not moving is what exposed it; had the win been assumed, a no-op would have
been reported as a fix.

Then, with both edits correctly applied, the total still did not move. That is
the second measurement, and it is the one that killed the lever. The first
measurement caught a broken edit; the second caught a wrong idea. Reporting
after either one alone would have been wrong.

The revert was done by hand rather than with `git restore`, which needs explicit
authorization in this worktree, and the file was confirmed byte-identical to
`HEAD` afterwards rather than assumed clean.

## The setup half, analysed: 1,564s, and no lever above 1.6%

Setup was 17.4% of suite CPU and every prior analysis in this campaign had
looked at CALL time. Aggregating setup-only per file:

    total setup : 1,564s across 1,771 files
     98.6s  test_acceptance_wall_catalogue     (already examined: batched wall run)
     78.2s  test_wheel_content_boundary        (already ruled out: build semantics)
     77.5s  test_dev_audit_report              (already optimised: shared build_report)

Below those sits a visually striking pattern -- nine-plus structural gates in
`src/cadrumo/tests/` each carrying a 16-24s setup, which looks exactly like the
same scan being repeated per module.

It is not. All of them already consume the SESSION-scoped `source_tree_ast`
prime, so none re-parses the tree; what each pays is its own WALK over the
shared 4,906 trees, looking for its own pattern -- skip/xfail policy, decimal
enrollment, `Any`-parameter rationale, clock usage, per-modelo carve-outs. The
expensive part is already shared; the remaining part is the analysis each gate
exists to perform.

Measured across the whole class rather than eyeballed:

    files consuming source_tree_ast : 19
    their total setup               : 145s = 9.3% of setup
                                    =  1.6% of the suite's 9,351s CPU

### Ruled out: fusing the nineteen walks

The available lever is the one already applied INSIDE a single module (the IVA
stem gates, three passes fused into one). Applied across these nineteen it would
mean a session-scoped combined inventory computing every pattern in one traversal.

Declined on the arithmetic and the coupling together. The ceiling is 1.6% of
suite CPU -- and less in wall clock, since the suite is CPU/worker bound and this
work is spread across workers already. Against that, nineteen independently
owned gates would share one traversal: a failure in the shared walk breaks all
nineteen at once, each gate stops being independently readable, and the next
author adding a structural gate inherits a fused helper rather than writing an
obvious loop.

Fusing three passes inside one module was worth it because they shared a file,
an owner and a failure mode. Nineteen gates across nineteen files share none of
those, and the payoff is an order of magnitude smaller.

### Where this leaves the setup angle

Exhausted. The three largest setups were already examined in earlier rounds, and
everything below them is either analysis a gate must do or is already sharing
the one genuinely expensive thing (the AST prime). No unexamined setup cost
above ~1.6% remains.

## First regression check against the baseline

The baseline reference exists so a round costs one profile and a diff rather
than a re-derivation. First use of it:

    CPU now 9,289s vs baseline 9,351s  (-0.7%)
    phase   call 7,586s | setup 1,597s | teardown 106s  (unchanged shape)

Every baseline file within +-10s, which is noise on this box. Two files sat
above 90s without being in the recorded top set:
`test_batch_ingest_runner.py` (93.8s, and 94.7s in the per-file aggregation that
produced the baseline -- not new), and
`application/tests/test_state_projection.py` (92.0s, which had been below the
78.6s cutoff of that aggregation).

### The candidate, investigated and cleared

Isolated and repeated, per the loop's own rule about repeating before reporting:
**71.39s and 71.50s**. So the 92.0s was contention, and the honest position is
that no isolated baseline for this file exists -- a regression cannot be claimed
from a contended figure against a contended cutoff.

Profiled anyway, since a reproducible 71.4s file is a target on its own terms:

    58.1s  n=31  core/resources/_repos/modelos.py:authority
    53.3s  n=1   registry/_authority.py:_load_validated_authority
    47.8s  n=1   registry/_authority.py:validate_registry

Thirty-one authority requests, ONE real validated load. The expensive thing is
already memoised; what the module pays is a single registry validation at 47.8s,
which every process needs before it can answer a projection question at all.
Nothing to share, and the discriminator (`n=1` against `n=31`) settled it
without a second experiment.

### What the check cost and what it bought

One profile (31 minutes) plus two isolated re-runs, to establish that the suite
has not drifted and that the one candidate is contention over an already-shared
cost. That is the intended steady state: the baseline turns an open-ended
"find something" round into a bounded comparison with a definite answer.

## Refactor analysis, and why no refactor was landed this round

The operator asked what could be REFACTORED rather than cached, which is a
different lever from everything above: not "compute once and share", but "stop
rebuilding the world to observe one fact".

### The shape, measured

`test_cli_workflow_verification` (103-191s) has a helper,
`_drive_workflow_round_trip`, that performs an entire workflow -- profile
create, auth configure/status/test, ledger import, overview, review -- and it is
invoked from **14 call sites, ~18 executions, one per test**. Each test then
asserts ONE field of a plain data bundle (`status_payload`,
`auth_status_payload`, `imported_payload`, ...). The backend fixture is
`autouse` and function-scoped, so nothing is reused.

`test_batch_ingest_runner` (107.4s) shows the same shape in miniature: eleven
tests take the same `(runtime_profile, batch_dir)` pair, and its first three
tests each call `_run(...)` on identical fixtures to assert different aspects of
one run -- the items reported, the refusal detail, the persisted draft.

The refactor is to build the world once per scenario and let tests observe
different facts of it: a class- or module-scoped fixture returning the outcome
bundle, with per-test assertions unchanged. Sharing the BUNDLE is safe by
construction where sharing a backend would not be -- the bundle is captured
data, not live state.

### Why nothing was landed

Both candidates failed a precondition, and the honest answer is that neither is
currently verifiable:

- `test_cli_workflow_verification` is **18 of 20 red** for tree-wide registry
  reasons. A module-scoped fixture there collapses eighteen individually-named
  failures into one setup error, which trades diagnostics for speed at exactly
  the moment the diagnostics are carrying information.
- `test_batch_ingest_runner` was the clean alternative -- 21 passed, twice, in
  the isolated baseline. Re-running it this round gave **5 failed, 16 passed**,
  and a repeat gave **21 passed** again. It is intermittently flaky, roughly one
  run in four.

A before/after comparison against a module that changes verdict between
identical runs cannot establish that a refactor preserved behaviour. The
repeat-before-reporting rule earned its place twice here: once by preventing a
false regression report, and once by disqualifying the target.

So the sequencing is stability first. Recorded as an available, quantified
refactor rather than a ruled-out one -- the lever is real and the payoff is the
largest remaining (roughly 103s to 10-15s on the workflow module alone), but it
should land against a module whose result is reproducible.

## Diagnosed: the batch-ingest flakiness is a leaked loopback endpoint

`test_batch_ingest_runner` blocks the largest remaining refactor because its
verdict is not reproducible. Four full-module runs gave 7 failed, 3 failed, 21
passed, 21 passed, and failures correlated with SLOWER runs (192.87s and 139.15s
against 116.44s and 107.82s).

The same test run ALONE passed 6 times out of 6, which rules the test itself out
and makes it an inter-test interaction.

Captured from a failing full-module run:

    runtime_reachable: False
    runtime_url: http://127.0.0.1:56455/api/tags
    connect_tcp.failed ConnectionRefusedError(10061, ...actively refused it...)
    AssertionError: a reachable reader must leave the lane open

Port 56455 is EPHEMERAL. `serving_loopback` binds `("127.0.0.1", 0)` so the OS
picks a free port, and `ThreadingHTTPServer` binds and listens before the URL is
yielded -- so a test INSIDE that block cannot get connection-refused. The tests
that fail are not inside it: only one test in the module uses the loopback
reader.

So a later test is probing an ephemeral URL belonging to an EARLIER test's
loopback server, after that server has been shut down and its port released.
The endpoint reaches the runtime through
`override_settings(cadrumo_llm_ollama_chat_url=chat_url)`, and `load_settings`
caches the constructed `Settings` -- a caching behaviour already documented
elsewhere in this tree, where "a plain `os.environ` mutation is invisible to the
in-process resolver once an earlier call already built and cached a `Settings`".
A cached instance outliving the context manager that installed it would produce
exactly this: a dead ephemeral URL, a refused connection, the runner taking the
paused path, and whichever tests required a reachable reader failing.

That also explains the load correlation. It is not that slowness causes failure;
it is that ordering and timing decide whether the stale URL is still installed
when a later test probes, and a contended run shifts both.

### Not fixed here

The remedy is in settings-cache lifetime around `override_settings`, which is
shared infrastructure reached by far more than this module, and the hypothesis
-- while it fits every observation -- has not been proven by instrumenting the
cache. Guessing at a fix in a caching seam used tree-wide is how a flaky module
becomes a flaky suite.

Recorded with the reproduction (run the full module repeatedly; roughly one run
in two fails under load) so an owner can act, and because it is the stated
precondition for the drive-once refactor: a before/after cannot establish
behaviour preservation against a module that changes verdict between identical
runs.

## CORRECTION: the leaked-endpoint diagnosis above is REFUTED

The entry above diagnosed the batch-ingest flakiness as an ephemeral loopback
URL surviving its context manager and being probed by a later test. That
hypothesis was instrumented and is WRONG.

A plugin recorded `cadrumo_llm_ollama_chat_url` at the setup of every test in
the module. All twenty-one tests see the DEFAULT endpoint, port 11434. Not one
sees an ephemeral port. There is no leak of the kind described.

Re-reading the failure with that constraint: the test that failed in the
captured run, `test_a_document_needing_a_reader_is_read_when_one_is_there`, is
the ONE test that uses the loopback reader -- so the refused connection happens
INSIDE its own block, not in a later test inheriting a dead URL. The earlier
reasoning inverted this: it treated "only one test uses the loopback" as
evidence that the failing tests were others, without checking which test the
captured failure belonged to.

The remaining puzzle is why a connection to a listening `ThreadingHTTPServer` is
REFUSED rather than answered (a request to an unserved path would be a 404, not
`ECONNREFUSED`), and that is now un-diagnosed rather than diagnosed. The
observations that stand are: the module fails intermittently, roughly one run in
two under load; the failing set varies; and the most-failing test passes 6/6
alone.

Recorded as a correction rather than an edit because the wrong diagnosis was
committed and may have been read. The lesson is the one this campaign keeps
relearning in new costumes: a hypothesis that explains every observation is
still a hypothesis, and this one survived precisely because it was never asked
to predict anything falsifiable until the instrument was built. It took one
plugin and one run to kill.

## Resource instrumentation: what the tests leave behind

The operator asked for instrumentation aimed at leaks and resource misuse
rather than speed. A per-test probe now records what a test still HOLDS after
its teardown -- OS handles, threads, inet sockets, RSS -- with a `gc.collect()`
first, so an object merely awaiting collection is not counted as a leak. Deltas
are taken around the whole test protocol, not the call phase, because a resource
released in teardown is ordinary use and only one held past it is a leak.

First run, across `test_batch_ingest_runner` plus a control module (35 tests):

    threads still held after teardown : 0 tests
    inet sockets still held           : 0 tests
    RSS across the module             : -5 MB (no growth)
    handles                           : 245 -> 287, net +42

Threads, sockets and memory are clean, which is worth stating plainly: three of
the four classic leak channels show nothing.

Handles do only ever rise, and the rise is concentrated:

    +25  test_a_poisoned_document_does_not_end_the_run        (first test in module)
    +23  test_a_paused_item_is_attempted_on_a_later_run
    +22  test_a_document_needing_a_reader_is_read_when_one_is_there
     +8  test_create_manual_transaction_returns_bucket_ref    (first test in control)

Every other test is zero or negative.

### What this does and does not show

The two first-in-module entries are ordinary lazy initialisation -- a process
opens its stores once -- and reading them as leaks would be the "big setup
figure is a bill, not a location" error in another costume.

The interesting pair is the two reader-using tests, each retaining ~22 handles
independently. If a single cached client pool were responsible, only the FIRST
would pay; two separate payments suggest a per-invocation client or file set
that is not closed. On Windows, handles are also the resource whose exhaustion
surfaces as unrelated failures much later, which is the shape of the
intermittent failures this module already shows.

That is suggestive, not proven. Four positive data points, no breakdown of
handle TYPE (psutil does not offer one on this platform), and no demonstration
that the growth is unbounded rather than plateauing. Proving it needs the reader
path exercised N times in one process while watching the count -- a contained
experiment, not a fix.

Recorded as a lead with its measurement and its limits, deliberately NOT as a
diagnosis, because the previous entry in this document was a confident diagnosis
that instrumentation then refuted.

## The handle-retention lead is refuted too, and that rules something out

The lead recorded above -- two reader-using tests each retaining ~22 handles,
suggesting a per-invocation client that is never closed -- was tested directly
by exercising each half N times in one process.

Server lifecycle, `serving_loopback` opened and closed six times:

    baseline                      174
    after start/stop 1            198   (+24)
    after start/stop 2..6         198   (unchanged)

Client side, eight requests through a fresh `httpx.Client` each time:

    server up                     202
    after request 1               214   (+12)
    after requests 2..8           214   (one blip to 217, back to 214)

Both PLATEAU. The cost is one-time initialisation of the socket, threading and
HTTP machinery -- paid by whichever test touches it first -- and it does not
grow with use. There is no leak.

That also explains the original observation without a leak: the two tests that
each showed ~+22 are the first to touch two DIFFERENT subsystems, not two
payments for the same one.

### What this buys

A negative result, and a useful one. Resource exhaustion is now ruled OUT as the
cause of this module's intermittent failures, which is worth more than another
plausible story: the remaining hypotheses no longer include the one that would
have been most expensive to chase on Windows.

The wider bill of health from the probe stands: zero threads and zero inet
sockets retained after teardown across 35 tests, RSS flat, and handle growth
bounded and explained.

### Two refuted leads in two rounds

The endpoint-leak diagnosis and the handle-leak lead were both killed by
instrumentation within a round of being written down. Both fitted every
observation available at the time. The difference between them is only that the
second was recorded AS a lead with its limits stated, so retracting it costs a
paragraph rather than a correction notice.

That is the working rule this campaign has converged on: a story that explains
the data is not a finding until it has predicted something falsifiable and
survived the test. Writing it down as a lead, with the experiment that would
kill it named, makes the retraction cheap and the discipline visible.

## The probe cost more than what it watched, and then swept a slice

The first attempt at a suite-wide leak sweep reached 9% in ten minutes. The
cause was the probe's own `gc.collect()` on every test: a full collection on
this heap costs around 100ms, and twenty-two thousand of them would have added
roughly 37 minutes to a 31-minute run.

That is precisely the failure the probe's own comment warns about -- it had been
written into the socket-counting branch and then violated two lines above. The
collection was there so an object merely awaiting collection would not be
counted as a leak; the trade is not worth it, because OS handles are held by
live objects and released on close, so collection timing barely moves them. A
few collectable stragglers are cheaper noise than distorting the run being
measured. Removed, along with the expensive `net_connections` call, which had
read zero on every test measured.

The trimmed probe runs 1,390 ledger tests in 122s, which is a tolerable
instrument.

### What the slice shows

    thread retainers                  : 0 of 1,390
    tests with any handle growth      : 50 of 1,390  (3.6%)
    top: +66 test_the_read_actually_reaches_the_loopback_endpoint
         +35 test_extracts_by_evidence_id_from_a_real_stored_pdf
         +31 test_an_unrepresentable_rate_refuses_and_names_the_accepted_rate
         +31 test_an_issued_document_records_the_billed_party_not_the_issuer

No thread leaks. The handle distribution is what per-worker first-touch
initialisation looks like: six workers, each paying independently for the first
socket, the first PDF reader, the first stored-evidence read, and so on. A leak
would show growth spread across MANY tests of the same kind rather than
concentrated in 3.6% of them, and the controlled experiment already showed both
the server and client halves plateau after one use.

So the ledger slice gets a clean bill on all four channels, and the instrument
is now cheap enough to point at the whole suite.

## Full-suite resource sweep: no leaks, and a 4x correction to the memory figure

The trimmed probe swept `src/cadrumo` plus `src/cadrumo-harness` under `-n auto`.

### Threads and handles: clean, definitively

    thread retainers across ~28,000 tests : 0
    tests with any handle growth          : 416 (~1.5%), across 241 modules
    handles per worker, min -> max        : ~222 -> 307..413

A worker ends a full run holding three to four hundred handles. That is bounded
and small, and it settles the handle question that two earlier rounds circled:
there is no leak. The 416 growth events are first-touch initialisation --
loopback reader, hardware probe, browser capture, notifications -- spread across
modules, and the per-worker totals never accumulate.

Zero thread retainers across the whole suite is the stronger result of the two,
because a stranded thread is the leak that most often turns a clean suite
order-dependent.

### Memory: peak RSS is 4.0-5.7 GB PER WORKER

    gw0 4,418 MB   gw1 4,563 MB   gw2 4,015 MB
    gw3 4,217 MB   gw4 5,748 MB   gw5 4,258 MB

At the six-worker default that is roughly **24-34 GB of peak resident set** for
one suite run.

This corrects a figure used repeatedly in this document. The worker-count
trade-off was argued from the session AST prime alone -- 1,216 MB per worker,
"7.3 GB at six workers" -- and treated as the memory cost of raising
`DEFAULT_WORKER_COUNT`. The measured peak is four to five times that. The prime
is a component, not the total; the rest is registry snapshots, compiled
authorities, cached catalogues and per-test stores.

The consequence is concrete: raising the worker cap from 6 to 12 on this box
would mean roughly 48-69 GB of peak RSS against 137 GB total, with peers already
holding a share. That is a materially different decision from the one the 7.3 GB
figure implied, and it is the only remaining wall-clock lever, so getting its
cost right matters.

Not called a leak: these are peaks, sampled at the tests that showed handle
growth, so the trajectory within a worker is not established. What is
established is the ceiling, which is what the worker-count decision needs.

### What the sweep bought

Three channels closed with measurements rather than argument -- threads clean,
handles bounded, and the memory ceiling now known instead of estimated from one
of its parts. The operator asked for instrumentation to find leaks and resource
misuse; the honest answer is that this suite has no leaks in the classic
channels, and its real resource story is a memory ceiling nobody had measured.

## Where the per-worker memory goes

The 4.0-5.7 GB per-worker ceiling was decomposed rather than left as a number.

### Session state is ~1.7 GB, and the AST prime is three quarters of it

Measured in one cold process, each step cumulative:

    bare interpreter                            19 MB
    import cadrumo                              +0 MB     19 MB
    import the CLI command tree                +97 MB    116 MB
    compiled registry tree (shared accessor)  +208 MB    324 MB
    validated registry authority              +127 MB    451 MB
    session AST prime (4,925 modules)       +1,272 MB  1,722 MB

So the session fixtures this campaign has been sharing account for about 1.7 GB,
and the AST prime alone is 1,272 MB of it -- which matches the 1,216 MB measured
independently earlier and is the one component worth knowing per worker.

### The other 2.3-4 GB accumulates during testing and is never released

Across the 1,390-test ledger slice in a single process:

    start 313 MB | 25% 667 | 50% 710 | 75% 752 | END 766 MB | PEAK 766 MB

RSS climbs monotonically and ENDS at its peak: +453 MB over the slice, roughly
0.33 MB per test, with most of it early and a slower climb after. Nothing comes
back. Extrapolated to a worker's ~4,700 tests on top of 1.7 GB of session state,
that is the observed 4-5.7 GB.

### It is NOT Python-object retention, on the evidence available

`tracemalloc` over a 35-test sample attributes only ~31 MB of surviving
allocations, dominated by import machinery (22.5 MB of module code objects),
then pydantic model construction and the registry compiled cache at 1-2 MB each.
Nothing in the Python heap accounts for hundreds of megabytes.

That points at native allocations (SQLite, cryptography, PDF parsing, libyaml)
or allocator pages the interpreter frees but does not return to the OS --
neither of which is a cache someone forgot to clear, and neither is fixable by
clearing one.

**Stated limit:** the trajectory was measured over 1,390 tests and the
attribution over 35, because `tracemalloc` pushed the full slice past a
ten-minute bound. A sample that small can miss an accumulating site that only
appears later, so this rules Python-object retention unlikely rather than out.
Settling it needs `tracemalloc` over a longer slice with a budget for the 2-3x
overhead.

### What it means for the only remaining wall-clock lever

The worker-count decision now has a decomposed cost rather than a single number:
about 1.7 GB of unavoidable session state per worker, plus roughly 0.33 MB per
test executed, ending at 4-5.7 GB. Raising the cap multiplies the session state
exactly and the accumulation proportionally to how the tests divide.

## Seeding a read-only suite once per file: `test_ledger_list_filter` 91.3s -> 53.9s

`src/cadrumo/entrypoints/cli/tests/test_ledger_list_filter.py` imported a
four-CSV ledger corpus in ten separate test bodies, then only ever listed it
back. Isolated, the file cost 91.30s.

Two changes, both landed:

- Two tests (`bogus=1`, a `--filter` token without `=`) imported the corpus for
  a refusal the filter-token parser raises before any ledger read. The corpus
  could not affect their outcome. Removed, and both now assert the typed
  `cli.ledger.filter.valid` failed condition rather than a bare non-zero exit --
  strictly stronger, because a bare exit-code check is also satisfied by an
  unrelated failure, which is precisely how those tests could have stayed green
  while the filter catalogue stopped refusing. 91.30s -> 81.17s.
- The remaining eight imports were replaced by one module-scoped fixture, on a
  new `scope` axis of `active_profile_isolated_backend_fixture`. 81.17s ->
  51.10s, repeated at 58.59s and 51.98s (mean 53.9s).

Order-independence is structural, not hoped for: an AST pass over the module
confirms the only mutating verb (`ledger import`) is in the fixture and every
test-level invocation is `ledger list`. The `scope` axis defaults to
`"function"`, so all 31 existing callers are unchanged; two sibling modules on
the default path were run to confirm (15 passed).

### Three corrections to what this audit previously recorded

- **The blocker was misattributed twice.** It is neither `live_fx_isolated_backend`
  nor `_isolated_state`. `_isolated_state` does not even apply to this module --
  it is autouse inside `_isolated_profile_storage_fixtures.py`, which is not a
  conftest, and the module imports only the backend fixture. The real constraint
  was that `active_profile_isolated_backend_fixture` produces a function-scoped,
  `tmp_path`-dependent fixture *by construction*, so no caller could opt out of
  per-test seeding. Naming the wrong fixture twice kept a tractable change
  looking blocked.
- **"89.3s of 155s importing the corpus nine times" was wrong on both numbers.**
  155s was measured under `-n auto`, so it carried contention; isolated the file
  was 91.30s. And there were **ten** import call sites, not nine. The isolated
  import costs ~3.9-5s, so the real prize was ~40s, not ~89s.
- **`pytest-randomly` is not installed in this environment.** Ordering is
  deterministic file order, and the `-p no:randomly` in earlier commands in this
  campaign was a no-op that neither randomised nor de-randomised anything. Any
  claim in this audit resting on "under random ordering" describes a plugin this
  tree does not have.

### Ruled out, so it is not re-chased

Making the corpus import itself cheaper is not available: `ledger import --file`
takes one file by CLI contract, so the four invocations cannot be collapsed, and
the corpus size is load-bearing (tests assert >=500 rows and a >=2-year span).

## HEAD does not validate its own registry

Independently of any performance work: at `505fab8304`, with a clean working
tree, `test_cli_workflow_verification` is 18 of 20 red and all 17 round-trip
failures share one cause -- `ERROR_CALCULATIONS_REGISTRY_VALIDATION`. The
messages are explicit authoring items (modelos 036 and 038 declare no export
layout; several modelo 100 revisions claim `filing` grade with families still
blocked pending evidence; two `orden-hac-1197-2025` articles cannot resolve a
corpus unit). This is the peer authority-grade sweep mid-campaign, not an
accidental break, and not this campaign's to fix.

It has two consequences worth recording. Any suite-wide durations profile taken
now measures a red tree and is not comparable with the 9,351s CPU baseline. And
the `test_cli_workflow_verification` refactor stays blocked -- not because a
module-scoped fixture would collapse eighteen named failures into one setup
error, which was the reason recorded earlier, but because a before/after cannot
demonstrate behaviour preservation against a module where every test already
fails.

## Two harness hazards that cost time this round

**A peer sweeper committed an in-flight edit mid-measurement.** Commit
`d6723a8240` picked up the half-finished two-file change: it took the factory
and the test module but not the fixtures file defining the symbol the test
module imports, so HEAD briefly could not collect that module. The subject it
was given was accurate, which is what makes this hard to notice -- the tell was
`git diff` returning empty on a file edited three times. Landing the missing
half immediately is the recovery; keeping the window short is the mitigation.

**The `pytest-of-hello/pytest-current` symlink `PermissionError` is no longer
cosmetic.** It aborted a verification run outright. `--basetemp=<private dir>`
is a reliable per-run workaround and costs nothing.
