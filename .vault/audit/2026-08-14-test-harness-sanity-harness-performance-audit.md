---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:663a772cb4190b9cc7cf210b69e3b3d3e151ed59f740b233727f2547d8ce5b62'
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

## Where the module-scope axis pays, and where it does not

Screening all 81 CLI test modules that use `active_profile_isolated_backend_fixture`
found only **6** that are provably read-only -- no mutating verb in any literal
argv, and no invocation whose argv could not be classified. The screen is
deliberately conservative: an `invoke_cached_cli` call whose argv is built
dynamically counts as *unclassifiable*, never as read-only, because a false
read-only verdict is what leaks state between tests. (An earlier, looser pass in
this campaign missed `_list_rows` for exactly that reason -- it builds its argv
in a loop.)

All six were measured: 24.59s, 6.49s, 3.85s, 3.15s, 2.59s, 1.27s. **None is
worth converting.** That is the useful negative result:

> The axis pays where a read-only suite performs expensive shared **seeding** in
> its test bodies. It does not pay for read-only-ness alone. Module-scoping the
> backend fixture by itself saves only the per-test storage-root and profile
> registration, about 0.27s per test.

`test_ledger_list_filter` qualified because it re-imported a four-CSV corpus ten
times, not because it was read-only. Read-only was the *permission*; the corpus
import was the *prize*. Do not re-chase the other five.

(Four of the six are also currently red on the registry-validation failure
described above, so their timings are the shape of a failing run.)

### The remaining prize is in the suites that DO mutate

Counting test functions that seed a ledger corpus -- directly, or through a
module-local helper whose body issues `ledger import` -- gives **141 per-test
seedings across 25 modules**, led by `test_ledger_bulk_classify` (23),
`test_ledger_import_ux` (16), `test_cli_workflow_verification` (13) and
`test_ledger_fx_import` (11).

**Method and its limit:** a helper counts if its body contains a literal argv
naming both `ledger` and `import`. That over-counts cheap seedings (a
two-transaction fixture costs far less than the four-CSV corpus) and misses any
seeding assembled dynamically, so 141 bounds the population rather than
measuring the time. It is a target list, not a saving.

Module scope is **unsafe** for nearly all of them -- they classify, split, merge
and remove -- so the shape that would fit is a **seed-once, copy-per-test**
fixture: build the world once, snapshot the isolated storage root, and give each
test a copy instead of re-running the import. That keeps per-test isolation
exactly as it is today while removing the repeated work, which is why it is
worth more than the scope axis. It is unproven: it needs checking against open
engine handles, WAL sidecars, and any absolute path baked into the encrypted
store. That validation is the next substantial piece, and it should not be
started as a side effect of a smaller change.

## The suite calls the live European Central Bank, and the gate against it is green

Profiling ONE CLI test (`test_ledger_persona_multicurrency`, cProfile, 28.25s
total) found the dominant cost is not work at all:

| symbol | calls | tottime |
|---|---|---|
| `_ssl._SSLSocket.read` | 54 | 8.90s |
| `_ssl._SSLSocket.do_handshake` | 54 | 2.30s |
| `socket.connect` | 54 | 2.14s |

**13.3s of 28.2s -- 47% of a single test -- is live HTTPS traffic**: 54 TLS
connections resolving FX rates against the ECB Data Portal, one fresh
`urllib.request.urlopen` per (currency, date) pair with no keep-alive
(`adapters/outbound/fx/_ecb_provider.py:199`).

### The discipline exists; only its enforcement is missing

This is not an undecided question. `_ecb_provider.py`'s module docstring states
the contract: the default transport reaches the live host unconditionally
because that is what the adapter is for, and holding a deterministic suite off
that host is a TEST concern -- inject `tests.ecb_stub.ecb_csv_fetch`, or declare
`aeat_live` and be selected by the live lane alone. `test_ledger_corpus_fidelity`
shows the sanctioned shape, with a declared corpus FX oracle held flat across
the corpus period so expected EUR values stay exact.

There is even a gate: `test_deterministic_tests_do_not_open_a_live_ecb_transport_door`.
**It passes.** Run on 2026-08-16 at `addcd09d8a`: 2 passed.

The blind spot is its reach. `_live_ecb_door_violations` AST-scans TEST modules
for a syntactic door -- `EcbReferenceRateProvider(...)` without a `fetch=`
keyword, or a call to `default_ecb_rate_provider`. The CLI persona suites name
neither. They drive the real Typer app, and the door is opened by PRODUCTION
code on their behalf (`entrypoints/cli/_ledger_import_cli.py:212`,
`entrypoints/cli/_ledger.py:417`). No door appears in the test module, so the
scan finds nothing and the gate reports clean.

The gate watches the front door; the traffic goes through the wall. Its name
claims "deterministic tests do not open a live ECB transport door", but what it
actually measures is "no test module SYNTACTICALLY NAMES one", and those two
statements came apart the moment a test reached the provider transitively.

### Why this outranks its own runtime cost

- The default lane depends on an external service being reachable and correct.
- Expected EUR figures derive from live market data, so a test's arithmetic can
  drift with the market rather than with the code.
- It is a live-network dependency sitting OUTSIDE the `aeat_live` lane that
  exists precisely to contain it.
- It is a candidate cause for the `test_batch_ingest_runner` flakiness recorded
  earlier in this campaign as undiagnosed. That investigation ruled out resource
  exhaustion and a leaked endpoint setting but never examined outbound sockets --
  the one hypothesis that predicts "fails about one run in two under load,
  passes six of six alone".

### Standing lesson

A gate keyed on a SYMBOL NAME cannot see a caller that reaches the symbol
through production code. Where the hazard is "this test reaches the network",
the honest instrument observes the SOCKET, not the source text. Any future gate
phrased as "tests do not do X" should be checked against the transitive path
before its green is believed.

### Correction: "47% of a test" does not generalise, and the runtime cost is small

The 47% figure above is real but was measured on a SINGLE-test run, where that
one test bore the whole per-process cost. Measuring the full CLI integration
lane with a socket counter gives the honest picture:

| measure | value |
|---|---|
| tests opening a remote socket | **5** (of 3,126 run) |
| total remote connections | 270 (54 each, one host: 80.90.16.29) |
| total `connect()` seconds | 11 |
| lane wall clock | 642.56s |

`connect()` is roughly a fifth of the network time (the profile splits 8.90s
read / 2.30s handshake / 2.14s connect), so the lane pays on the order of ~55s,
about **1-2% of the CLI lane -- not 47%**.

The reason is `default_ecb_rate_provider`'s `lru_cache(maxsize=1)` plus the
provider's own per-(currency, date) memo: the first FX-bearing import in a
worker process pays, and every later one in that process is free. With six
workers the suite pays it at most six times, and exactly five modules did.

**The performance claim was wrong; the correctness claim is not.** All five tests
carry `integration`, not `aeat_live`, so the lane genuinely depends on an
external host being reachable and correct, and expected EUR values still derive
from live market data. What that buys in practice is variance rather than bulk
cost: `test_ledger_persona_multicurrency` ran 14.63s, 14.89s, 14.99s, 22.67s and
32.48s on **identical code** -- a 2.2x spread with no code change between runs.

### That variance invalidates the before/after deltas quoted earlier

The single-run figures recorded above for the seed-once/copy work sit inside
that noise band and must not be read as measurements:

| module | quoted before -> after | re-measured median (3 runs) |
|---|---|---|
| `test_ledger_persona_asesor_review` | 74.03s -> 48.10s | **52.59s** (44.74-54.73) |
| `test_ledger_persona_yearend_m100` | 101.22s -> 80.50s | **37.25s** (36.29-44.02) |
| `test_ledger_persona_multicurrency` | 38.08s -> 32.48s | **14.89s** (14.63-22.67) |

The yearend "after" of 80.50s is more than twice its own median. Every one of
those numbers was a single sample of a bimodal distribution.

What survives is the STRUCTURAL claim, which is deterministic and needs no
timer: the number of corpus seedings per module went from one-per-test to one
(10 -> 1, 9 -> 1, 7 -> 1), and isolation is unchanged because each test still
gets its own storage root. Prefer that metric here. **Any runtime comparison in
a module that imports FX-bearing rows needs medians over at least three runs;
a single before/after pair cannot clear the network noise.**

## Importing the CLI parses a locale catalogue, and tests always take the slow path

`entrypoints/cli` carries **142 module-level `tr()` calls across 52 files**. The
first one executed forces the whole locale catalogue to be resolved *while the
CLI package is being imported* -- before any command runs. Traced from a probe
that wraps `_packaged_locale_map` and reports only genuine cache misses:

```
PARSE locale='en' seconds=2.253
  _ledger.py:54   from ._bienes_inversion_cli import register_bienes_inversion_commands
  _bienes_inversion_cli.py:39   help=tr(
```

There is already a defence: `_packaged_locale_map` is `lru_cache`d, and beneath
it `_catalogue_cache` persists the flattened map keyed by source digest. It
works -- in production. It cannot work in tests, because `catalogue_cache_path`
resolves through `storage_path(StorageCategory.LOCALE_CATALOGUE_CACHE)`, i.e.
`<storage-root>/cache/locale-catalogue`, and every test installs a fresh
isolated storage root. The cache is written into a directory that is discarded
before anything can read it.

Measured directly, importing `cadrumo.entrypoints.cli` in a clean process:

| storage root | import seconds |
|---|---|
| real (cache present) | 0.587, 0.624 |
| empty (cache absent -- every test) | 1.464, 1.455 |

**~0.85s per process**, and the in-test probe measured the parse itself at
2.253s. Variance is negligible because no network is involved; unlike the FX
numbers, these can be trusted from two samples.

### Sized, and deliberately NOT chased

The `lru_cache` makes this **once per process, not once per test**. Six workers
means roughly 5-13s per suite run against a ~1,900s wall clock -- **well under
1%**. A session-scoped warm-up fixture (populate `_packaged_locale_map` before
isolation installs a storage root) would recover most of it for no production
change, and is recorded here as available rather than done: it is not worth a
shared-harness change at that size.

Two things are worth carrying forward regardless of the timing:

- **The write is not the waste; the read is.** An earlier hypothesis in this
  session -- that the never-read cache file costs meaningful write time -- is
  wrong and should not be re-chased: `write_catalogue_cache` measured 0.117s
  for both locales. What is lost is the 2.253s READ that never happens.
- **`tr()` at module scope makes importing a package do I/O.** A help string
  evaluated at decoration time turns `import cadrumo.entrypoints.cli` into a
  catalogue load. Deferring those 142 call sites behind a lazy string would make
  CLI import independent of the locale layer entirely. That is a production
  change to every CLI help surface, so it belongs in a decision record rather
  than in a performance sweep, and its value is operator-facing startup latency
  (`aeat --help`) more than suite time.

## `aeat app modelo list` takes 33.6s, and 90% of it is loading the registry authority

Taken from the durations tail rather than by inference:
`test_cli_startup_smoke::test_app_modelo_list_starts_without_unlocking_active_profile`
is 29.70s in the CLI lane, and the module makes exactly ONE `subprocess.run`.
So a single cold `aeat app modelo list` IS the test. Timed directly against an
empty storage root: **33.62s, 33.67s, 33.80s, 33.31s, 33.44s** -- one CLI
command listing modelo codes.

Split by a sampling profiler (see the correction below for why not cProfile):

```
import=1.31s   run=31.93s
CUMULATIVE  90.6%  domain/calculations/registry/_authority.py:98(load)
                   via core/resources/_repos/modelos.py:38(_resolve_authority)
SELF        17.2%  pathlib open
            16.2%  ntpath.realpath
            10.3%  read_text
             9.7%  pathlib stat
             7.7%  core/_directory_scan.py:307(_read_entries)
             4.5%  zipfile read      4.1%  bs4/lxml feed
             1.8%  pypdfium2 get_page  1.3%  pypdfium2 get_textpage
```

Listing modelos resolves the **full validated registry authority**: thousands of
TOML fragment reads, `realpath` on each, zip archive reads, HTML legal-corpus
parsing through lxml, and PDF text extraction through pypdfium2. None of that is
needed to print `code / title / cadence / domain / revisions`.

This is the shape of the operator complaint that opened this thread: a command
scaffold should not pull a corpus. The remedy direction is a lightweight
metadata projection for listing surfaces, or deferring corpus and PDF evidence
until a verb actually needs it -- an architecture decision, not a sweep, and
recorded here for one.

### Correction: cProfile blamed the wrong function by two orders of magnitude

cProfile attributed ~30s of the 33.6s run to `_normalise_header_cell`
(16,149,174 calls) and its 97,432,518 `str.replace` calls. **That was an
instrumentation artifact.** cProfile charges per CALL, and the run took 78.28s
under it against 33.6s real -- roughly 45s of overhead, landing almost entirely
on the highest-call-count frames.

The disconfirming test was direct: memoising the function changed the real cold
run by **nothing** (33.80 / 33.31 / 33.44 against 33.62 / 33.67). Sampling then
put the frame at **1.4%**, not 90%.

The memoisation was kept, but on its own evidence rather than that profile: 2.50x
on the function (385ns -> 154ns per call), 71,994 cache hits against 6 misses,
byte-identical output across 5,527 inputs. Its contribution to the cold run is
below wall-clock noise.

**Standing lesson: on a call-count-heavy workload, cProfile measures the
profiler.** Any hot spot it reports with millions of calls must be confirmed by
sampling, or by removing the work and re-timing, before it is believed -- and
certainly before it is reported. Both false headlines in this campaign (the ECB
47%, and this) came from reading a profile without checking the instrument.

## Shared registry disk cache: real standalone, no measurable suite win

`aeat app modelo list` against a fresh storage root pays a cold registry
compile. The compiled artefact is cached on disk, and the cache is relocatable
through `CADRUMO_REGISTRY_DISK_CACHE_DIR`, which `_run_cli_cold` propagates to
its children (it filters only `AEAT_`-prefixed variables). That looked like a
free lever: share one warm compile across every process.

Standalone it is real:

| configuration | seconds |
|---|---|
| everything cold | 32.12, 33.31, 33.44, 33.62, 33.80 |
| fresh storage root + SHARED registry cache | 25.14, 24.76, 24.74 |
| fully warm, same storage root reused | 23.33, 23.65 |

**~8.5s per cold CLI invocation**, about 80% of the total achievable cache
benefit, with no production change.

The on-disk artefacts show what is being moved: a 23.1 MB registry pickle, a
32.8 MB corpus-text cache and a 5.1 MB locale catalogue. Even fully warm, listing
modelo codes deserialises ~56 MB, which is why the warm floor is still 23.3s.

### It does not transfer to the suite, and the reason is already-solved

Applied to real modules, before and after are indistinguishable:

| module | baseline | with shared cache |
|---|---|---|
| `test_cold_start_wizard_registration` | 64.39, 64.80, 64.27 | 64.40, 64.67, 64.67 |
| `test_ledger_persona_yearend_m100` | 43.06, 35.80, 43.00 | 35.87, 42.94, 35.57 |

`src/cadrumo/conftest.py:50` pins `CADRUMO_LOCAL_STORAGE_ROOT` to a STABLE
collection root, so the registry cache is already warm in the pytest process
before any test installs its isolated root. The lever was pulled long ago; there
is nothing left to recover in-process.

The remaining cold consumers are subprocess spawns that set their own storage
root — and the ones in the durations tail
(`test_cold_start_wizard_registration`, `test_cli_startup_smoke`) currently FAIL
on the registry-red HEAD, so their timings are error paths and cannot be
optimised against. **Do not re-chase this until the registry validates.**

### Two measurement hazards this reconfirms

- The yearend numbers are **bimodal**: every run lands near 35.7s or near 43.0s,
  in BOTH arms. Three samples of a two-mode distribution produce whatever median
  the draw happens to give — the apparent 43.0 -> 35.87 "improvement" above is
  pure sampling. For any module importing FX-bearing rows, three runs are not
  enough; separate the modes or take many more samples.
- **A red tree is not an optimisable tree.** With 636 of 3,126 CLI-lane tests
  failing, much of the tail measures failure paths. Timings taken now describe a
  program that is not the one that will ship.

### Verified: the copy-per-test fixture really does copy, and the clones are reclaimed

Checking the disk cost of `seeded_isolated_backend_fixture` nearly produced a
false alarm. The seeded origin is **7.4 MB / 18 files**, but a basetemp tree
after a completed run contains ONLY `seeded-origin0` -- **zero** per-test
`seeded-world` clones. Read naively that says the function-scoped fixture never
ran, which would mean the suite had no per-test isolation at all.

`--setup-show` settles it:

```
SETUP    M _isolated_backend_origin (fixtures used: tmp_path_factory)
    SETUP    F _isolated_backend (fixtures used: tmp_path)
    TEARDOWN F _isolated_backend
```

Both run, in the right order and scopes. The clones are created per test and
then reclaimed by the harness's `_release_settings_storage_directories`
teardown, so the finished tree shows none. Disk cost is one 7.4 MB copy live at
a time, measured at 0.04s.

**An empty directory tree is not evidence that a fixture did not run** when the
harness cleans up after itself. Ask the fixture graph, not the filesystem.

## The suite is ~1/5 red, and that bounds what this loop can measure

Measured at `d9844e789b`, both lanes:

| lane | red |
|---|---|
| CLI integration | 636 failed + 60 errors of 3,126 -- **20.3%** |
| unit (first 10,944 outcomes) | 1,112 failed + 718 errors -- **16.8%** |

The cause is the same registry authority-grade campaign recorded above.
`test_cli_workflow_verification` is still 18/20 red at this HEAD.

**A red test measures its error path, not its work.** Roughly one test in five in
this tree currently times something that will not exist once the campaign lands,
so any tail mined now is partly fiction, and any before/after spanning those
tests is uninterpretable. This is a bound on the loop, not a reason to stop: it
means prefer STRUCTURAL metrics (seedings removed, calls avoided) over wall
clock, and prefer modules verified green individually.

## Suite-wide worklist for seed-once/copy-per-test

Derived statically, so it does not depend on the tree being green. A module
qualifies when a module-level helper whose name suggests seeding
(import/seed/register/create/add/populate) is called from at least three of its
own test functions:

**194 modules, 1,294 per-test seedings.** The head of the list:

| seeded / tests | module :: helper |
|---|---|
| 25 / 25 | `entrypoints/cli/.../test_maternidad_meses_reach_the_calculate_path.py :: _seed_natural_person_profile` |
| 23 / 29 | `application/auth/tests/test_certificate_sources_check.py :: _register_operator_profile` |
| 22 / 31 | `entrypoints/cli/.../test_ledger_bulk_classify.py :: _import_two_transactions` |
| 21 / 31 | `application/auth/tests/test_operator.py :: _register_operator_profile` |
| 18 / 18 | `entrypoints/cli/.../test_modelo_100_descendiente_entry_surface.py :: _seed_natural_person_profile` |
| 17 / 17 | `application/auth/tests/test_clave_credential_resolution.py :: _register_profile` |
| 16 / 20 | `application/tests/test_state_projection.py :: _register_active_profile` |
| 16 / 17 | `entrypoints/cli/.../test_ledger_evidence_confirm_cli.py :: _add_structured_evidence` |

Two things make this list better than the CLI-only view it replaces:

- The `application/auth` cluster seeds by **registering a profile**, which this
  campaign already measured as the single most expensive fixture step (17.44s
  before the KDF-calibration fix, 2.20s after). Those modules sit outside the
  CLI lane, so they are candidates for being green and measurable while the
  registry campaign is in flight.
- `test_maternidad_meses_reach_the_calculate_path` seeds in **25 of 25** tests
  and is already in the CLI durations tail at 24.33s.

**Method and its limits:** the helper must be module-level and matched by NAME,
so this misses seeding written inline in each test, seeding through an imported
shared helper, and any helper named outside the hint list; and it counts a
two-row CSV the same as a 514-row corpus. It is a ranked candidate list, not a
saving. Each entry still needs its seed cost measured before conversion --
`test_ledger_bulk_classify` seeds two inline EUR-only rows, so its 22 seedings
may be worth far less than the eight full-corpus imports already converted.

## Profile registration: measured, decomposed, and ruled out as a caching target

`register_minimal_profile` is the seeding primitive behind the largest cluster
on the worklist. Measured precisely by wrapping it (29 calls in
`application/auth/tests/test_operator.py`): **8.01s of that module's 21.15s --
38% -- at 0.276s per call.** Suite-wide the shape is called on the order of
1,294 times, so roughly 350s of CPU.

Profiling one registration showed what looked like textbook redundancy inside a
SINGLE call: 8 `_profile_repository.load`, 4 `_capsule_record.load`, and 3
`resolve_active_profile_output_language` -- the last performing a full encrypted
workflow-state load each time, because it is registered as the `core.i18n`
active-language callback and reads `workflow_state_repository().load()` on every
resolution.

**The caching lever is a correctness bug, and the probe proved it before it was
built.** Fingerprinting what each load RETURNED, rather than counting calls:

```
workflow_state loads: 4
distinct state fingerprints: 4
redundant consecutive loads: 0 of 4
```

Every load observes different state, because profile creation writes between
them. A memo keyed on "the active profile's language" would serve one of those
four states to a caller expecting a later one. **Do not re-chase caching inside
the registration path**; its cost is the writes it performs, not repeated reads.

The general rule this instance illustrates: **a repeated read is only redundant
if it returns the same value.** Counting calls identifies candidates; comparing
returned values is what distinguishes a cache from a stale-data defect. Count,
then fingerprint.

(A third cProfile inflation datum, consistent with the earlier correction: the
single test measures 2.09s unprofiled and 25.88s under cProfile.)

### Why the module conversion was not done either

`test_operator.py` is 29-of-31 seeded and looked like the next conversion, but
`test_auth_status_preserves_the_active_profile_typed_verdict` asserts
`verdict.failed_condition_id == "profile.active.pointer_registered"` -- it
depends on the profile being ABSENT. A seeded module-scoped origin would not
fail it loudly; it would invert what it proves. Converting the module therefore
requires splitting that test out, and the repo's supplementary-marker precedents
(`perf`, `external_tool`, `os_keychain`) are all LANE-SELECTION labels, so a
"needs an unseeded world" marker would be a category error against the
marker-integrity gate. Deferred deliberately rather than forced.

**Check every candidate module for absence-dependent tests before converting.**
The seeded-count metric on the worklist cannot see them: a test that requires a
missing precondition looks identical to one that simply does not seed.

## The ECB tests violate the written marker contract, not just a convention

`pyproject.toml` defines the lanes explicitly:

- `unit`: "deterministic offline tests scoped to one owner; owned local
  processes are allowed, **external networks and services are not**"
- `integration`: "**deterministic** in-process tests that cross architectural
  layers"

The five tests reaching the live ECB Data Portal are marked `integration`. They
are neither deterministic (14.63-32.48s on identical code) nor free of external
services. This is not an unwritten convention being bent -- it is the declared
meaning of the marker they carry, and `aeat_live` exists for exactly this case.

## The seeding worklist, corrected twice, is worth about 1% -- stop grinding it

The worklist recorded earlier (194 modules, 1,294 per-test seedings) was an
overcount, for two reasons found by trying to convert its top entries.

**First correction -- parameterised seeding is not repeated seeding.**
`test_clave_credential_resolution` is 17-of-17 seeded and green, which put it at
the top of the "clean" candidates. 16 of those 17 calls pass **per-test
overrides**: each test registers a differently-configured profile. There is no
shared world to seed once. Re-running the scan with argument-shape awareness
(a site counts as uniform only when every call passes identical literal
arguments):

| | sites | seedings |
|---|---|---|
| uniform -- convertible | 132 | **722** |
| parameterised -- NOT convertible | 111 | **703** |

**Roughly half the original figure was never convertible.**

**Second correction -- absence-dependent tests are invisible to the metric**, as
recorded above for `test_operator`. A test requiring a missing precondition
looks identical to one that merely does not seed.

### And the surviving half is not worth bespoke conversion

Measured seed costs across the campaign:

| seed | cost each |
|---|---|
| four-CSV ledger corpus import | 4-5s |
| `register_minimal_profile` | 0.276s |
| `isolated_runtime_profile` per-test fixture | 0.257s |
| `test_manual_add_idempotency` seeds | negligible (whole module 1.31s / 15 tests) |

The three conversions already landed took the expensive head of that
distribution -- full-corpus imports, 10/9/7 per module. What remains is
~722 seedings at roughly 0.25s, so on the order of **180s of CPU, of which
perhaps half is recoverable: ~1% of the 9,351s suite**, spread over 132 modules.

Each conversion is also bespoke, not mechanical. Three different isolation
families are in play -- `active_profile_isolated_backend_fixture`,
`bucket_session_storage_fixture` and `isolated_runtime_profile` -- and a
copy-per-test variant must be built per family. Every candidate additionally
needs checking for absence-dependent tests and for parameterised seeds, both
invisible to the count.

**Ruled out: do not convert the seeding tail module by module.** The lever is
exhausted at the head. It becomes worth revisiting only if a GENERIC
copy-per-test wrapper is built over the shared shape (a context manager that
roots storage at `tmp_path`), which would cover all three families at once --
and that is worth doing only alongside a target bigger than 1%.

Candidates verified and rejected this round, so they are not re-tried:
`test_maternidad_meses_reach_the_calculate_path` (25 uniform seedings, RED:
22 failed), `test_certificate_sources_check` (24, 2 failed), `test_amend_flow`
(13, 26 failed), `test_llm_review_workflow` (9, red), `test_operator` (21,
green but absence-dependent), `test_clave_credential_resolution` (17, green but
parameterised), `test_manual_add_idempotency` (10, green but seeds are free).

## Authority load, decomposed: fingerprinting is ~1s, compiling is the floor

Aimed at the CLI load time directly. `aeat app modelo list` against a fresh
storage root, measured across three different HEADs during the investigation
(`d9844e789b`, `05e1b2bc92`, `53cb5dad74`) -- the end-to-end numbers are stable
even though the registry tree moved underneath:

| | seconds |
|---|---|
| cold (no caches) | 33.62, 33.31, 33.44, 33.02, 32.90 |
| warm (caches present) | 23.33, 23.65, 24.37, 23.51 |

### Where it goes

`ValidatedRegistryAuthority.load` computes four fingerprint collections before
it can consult any cache, because they ARE the cache key. That was the obvious
suspect for the ~23s warm floor, and it is **wrong**:

| phase | cold | warm |
|---|---|---|
| `collect_registry_tree_fingerprints` (18,847 entries) | 0.83-0.87s | 0.83s |
| `collect_convenio_fingerprints` (9) | 0.002s | 0.002s |
| `collect_supplementary_orden_fingerprints` (1) | 0.000s | 0.000s |
| `collect_source_evidence_fingerprints` (2,398) | 0.074-0.085s | 0.076s |
| **all fingerprinting** | **~0.93s** | **~0.93s** |
| `_construct_authority` (compile the tree) | **10.1-10.5s** | **2.9s** |

Fingerprinting 21,255 entries costs under a second and is not worth touching.
**The compile is the floor**: 10.2s cold, and still 2.9s warm with the 23.1 MB
registry pickle cache serving it. Sampling attributes 90.6% of the whole cold
run to `_authority.load`, which these numbers now decompose.

### Validation is designed NOT to be paid per invocation

`_load_validated_authority` consults a verdict cache before validating:

```
if registry_validation_is_certified(root, verdict_key=..., registry_fingerprints=...):
    authority.mark_registry_validated()
else:
    authority.validate_registry()
    certify_registry_validation(root, verdict_key=...)
```

Two verdict stores exist: a **shipped** `aeat-validation-verdict.json` stamped
beside the bundled registry root by the release build, and a writable
per-storage-root file under `<storage-root>/cache/registry-verdict`. So the
multi-second re-validation is meant to happen once.

Neither is available here. This checkout is an authoring tree, so
`bundled_verdict_path` returns `None`; and the per-storage-root verdict is only
written on SUCCESS, so while the registry is red **no verdict can ever be
certified** and every process that reaches validation pays it again. One
measurement at the earlier HEAD put that at **~17.6s** (28.76s total minus
10.5s compile minus 0.95s fingerprinting).

Note the same storage-root scoping as the locale catalogue: even on a green
tree, a test installing an isolated storage root cannot reuse a verdict written
by another test, and neither can a cold CLI subprocess.

### What is durable, and what is not

Durable -- repeated, tight, and stable across three HEADs: the end-to-end cold
and warm figures, the ~0.93s fingerprinting, the 10.2s/2.9s compile, and the
90.6% sampling attribution.

**Not durable:** the exact validation share, and which phase currently raises.
The registry tree changed three times during this investigation, and at the
latest HEAD `_construct_authority` itself raises at ~10.1s before validation is
reached, where at the earlier HEAD construction succeeded and validation ran.
Any finer attribution than the table above is measuring a tree that no longer
exists. **Do not chase the compile/validate split further until the registry
is green and still.**

### The architectural point, which survives all of it

Rendering `code / title / cadence / domain / revisions / local_work` requires
compiling the ENTIRE registry authority -- every modelo, every revision,
formulas, bindings, casillas, export layouts and record designs -- and normally
validating it too. Even with every cache warm and a verdict certified, the floor
is compile (2.9s) plus CLI import (~1.5s): **a listing command cannot get below
several seconds while it goes through the full authority.**

The remedy is a metadata projection for listing surfaces: the fields `modelo
list` renders are declared in the authoring TOML and need neither formula
compilation nor record-design parsing. That is an ADR, not a sweep -- it adds a
second read path over registry data, and the rule that snapshot construction is
authority-owned exists precisely to stop those multiplying.

## The compile is first-touch I/O over 17,526 files, not loader inefficiency

Sampling `_construct_authority` (not cProfile -- this workload is call-count
heavy and cProfile has already lied twice here):

| self | frame |
|---|---|
| 38.6% | `pathlib open` |
| 14.3% | `core/_directory_scan.py:307(_read_entries)` |
| 13.4% | `pathlib stat` |
| 11.6% | `read_text` |
| 8.0% | `bs4/_lxml.feed` |
| 2.9% / 2.8% / 2.7% | `os.walk` / `glob` / `realpath` |

**~80% is filesystem work.** Cumulatively: `load_registry_tree` 90.3%,
`_load_all_modelo_definitions` 72.3%, `_merge_revision_directory` 51.1%, and
**`rtoml.load` / `read_toml` 50.0%** via `_read_single_revision_table`.

Two candidate explanations, both testable, both wrong in the interesting way:

- **Loader inefficiency?** No. `_read_entries` already uses `os.scandir` with a
  materialised list -- the efficient shape, and deliberately so (its docstring
  explains the handle is closed before the caller sees an entry, to survive a
  Windows sharing violation). There is no obvious redundant work to remove.
- **The `Y:` backing share?** Not established. Loading the same tree from the
  share and from a local-disk copy gave share 10.14/1.19/2.12s and local
  15.70/4.78/4.59s -- i.e. the share appears FASTER, which is not credible. The
  arms ran in sequence, the local copy was written immediately before its arm,
  and the OS page cache cannot be dropped here without admin rights. **That
  comparison is confounded and proves nothing; do not cite it either way.**

What the same data does establish, because it holds inside BOTH arms
independently: the first load is **10.14s** (share) and **15.70s** (local), and
the second and third are **1.19-2.12s** and **4.59-4.78s**. Same code, same
tree, caches cleared between every run. **The cold compile is dominated by
first-touch I/O; once the operating system holds the files, the identical work
costs a fraction.**

### What that means for the remedy

The registry tree is **17,526 files** (18,847 fingerprint entries). Nothing in
the loader is wasting time: it is reading seventeen thousand small TOML
fragments because that is what compiling the authority requires.

So a faster loader is not the lever, and neither is a bigger cache -- the
existing 23.1 MB pickle already collapses a warm compile to 2.9s. **The lever is
touching fewer files**, which is exactly the metadata-projection proposal
recorded above, and this measurement is its quantitative support: printing
`code / title / cadence / domain / revisions` currently costs a first-touch read
of a seventeen-thousand-file tree.

**Ruled out, do not re-chase:** micro-optimising `_directory_scan`,
`_read_entries`, or the TOML read path; and any attempt to attribute the cold
cost to the `Y:` share without a cache-dropping benchmark that this environment
cannot run.

## C-level delegation in the compile path: already done, and hand-rolling it is slower

Directive: on load-bearing paths delegate to the fastest C-level calls and cache.
Applied to the registry compile, whose hot path is `read_toml` (50% cumulative,
~17.5k fragments). Two layers looked like Python where C exists:

1. `rtoml.load(path)` appeared to read through `pathlib.Path.read_text`, and
   `pathlib open` is the largest single self-time frame in the compile.
2. `for key, value in loaded.items(): raw[key] = value` is a Python-level copy
   of every parsed mapping, where `dict(loaded)` is the same operation in C.

Benchmarked over 3,000 real registry fragments, warm cache, five repeats, with
an equality gate asserting every arm produces identical output on every fragment
before any timing:

| arm | median | vs current |
|---|---|---|
| current: `rtoml.load(path)` + Python copy | **0.781s** | — |
| builtin `open(...,'rb')` + `rtoml.loads` + Python copy | 0.895s | **0.87x (slower)** |
| builtin `open(...,'rb')` + `rtoml.loads` + `dict()` C copy | 0.939s | **0.83x (slower)** |

**Both "optimisations" are slower.** `rtoml` is a Rust extension and its
`load(path)` performs the read on the Rust side, so replacing it with a Python
read plus `loads` ADDS a layer rather than removing one; the profile's
`read_text` attribution comes from other callers on the same stack, not from
inside `rtoml.load`. `dict(loaded)` did not beat the explicit loop either.
**Not shipped.** Per-arm spreads (0.712-0.955s) overlap, so the honest reading is
"no win available", not "current is 15% better".

**Ruled out, do not re-chase:** rewriting the registry TOML read path for
C-level delegation. It is already delegated.

### The remaining C-level candidate, and why it is declined

`bs4/builder/_lxml.py:feed` is 8.0% self-time in the compile:
`_orden_anual_html.py:184` runs `BeautifulSoup(markup, "lxml")` over BOE annual
Orden HTML, and `_m303_orden_manifest.py:48` records that extracting one Orden
means a full BeautifulSoup parse. Going to `lxml.html` directly is typically
several times faster, because bs4 builds a Python object tree over lxml's C tree.

Declined on risk-versus-reward, not on difficulty: it is a rewrite of a
**legal-corpus extraction** (IVA módulos indexes out of BOE Orden text) from
bs4's `find`/`select`/`get_text` onto lxml's `xpath`/`text_content`, in a path
whose output feeds regulatory grounding. The reward is ~8% of a 10s cold compile
that happens once per process and is already collapsed to 2.9s warm by the
pickle cache. If it is ever taken, it needs byte-identical output proven across
every bundled Orden, and it belongs in its own change rather than a performance
sweep.

### Standing conclusion for this path

The compile is already Rust-parsed (`rtoml`), already `os.scandir`-based, already
`lru_cache`d per modelo directory and per tree, and already served warm from a
23.1 MB pickle. There is no idle C-level delegation left in it. **Its cost is
the 17,526 files it touches**, which is a shape problem, not an implementation
one -- see the metadata-projection proposal above.

## Directory-scan deduplication: one fold landed, one reverted, the rest capped at 0.26s

The warm registry compile is ~1.23s with **58.8% of self time in
`core/_directory_scan.py:_read_entries`** and 92.5% cumulative under
`discover_modelo_sources` -- discovery, not TOML parsing. Instrumenting the
scanner over a warm compile:

```
_read_entries calls      : 3,659
distinct directories     : 1,259
REDUNDANT re-scans       : 2,400  (65.6%)
```

Every section directory was listed three times.

### Landed

`discover_modelo_sources` listed `modelos/` three times (validate, `*.toml`,
subdirectories) and `_discover_revision_sources` did the same per modelo. Each
validating pass had already `stat`'d every entry to classify it, so the later
listings recomputed something in hand. Both validators now return their
classification: **115 fewer listings per compile, adding no syscalls.**

Wall clock: **1.29s median of five (1.21-1.36)** against a 1.33s single-sample
before. Deterministic work removed; **not** a measured speed-up, and recorded as
such.

### Reverted, with the reason pinned at the call site

The same fold over SECTION directories -- the most numerous in the tree -- cut
listings 32% (3,659 -> 2,493) and made the warm compile **slower**: 1.49s median.

`scan_directory(select=...)` and `pattern=...` classify from
`os.DirEntry.is_dir()`, which `os.scandir` already populated, so they never
`stat`. One scan classified in Python via `Path.is_dir()` costs **one stat
syscall per entry**. Fewer listings, more stats, net loss.

**The lesson, which cost a full cycle: a reduced call count is not a reduced
cost.** The metric that looked like the win was measuring the wrong resource.
Dedup only pays when the removed call is more expensive than the bookkeeping
that replaces it -- and `DirEntry`-based selection is already close to free.

### The rest of the redundancy is capped, so stop here

There is a correct version of the section fold: one recursive
`select=ALL` walk, grouped by parent, reusing `DirEntry` classification and so
adding no stats. Before writing it, the ceiling was measured:

| | |
|---|---|
| time inside `_read_entries` | **0.391-0.411s** (32-33% of the warm compile) |
| recoverable if ALL 2,285 redundant scans vanished at zero cost | **~0.26s** |

**~0.26s of a ~1.23s warm compile** -- and that compile is 2.9s inside a CLI
invocation that costs 24s warm / 33s cold. A perfect dedup of every remaining
re-scan cannot move the number the operator sees.

**Ruled out: the recursive-walk scan-dedup refactor, and directory-scan
deduplication generally.** The ceiling is measured, small, and does not justify
restructuring revision-fragment validation. The CLI load-time lever remains the
metadata projection recorded above, not the scanner.

## `test_batch_ingest_runner`: 73% of it is failing to connect to a local LLM, once per test

The flakiness recorded as undiagnosed earlier in this campaign is diagnosed.

Sampling the module (never cProfile here) puts **68.4% of self time in
`socket.create_connection`** -- 28,231 of 41,265 samples. A socket counter that
records LOOPBACK as well as remote targets gives the detail:

| target | connections |
|---|---|
| **127.0.0.1:11434** (Ollama default) | **65** |
| 127.0.0.1:1 (a deliberate unreachable sentinel, one test) | 5 |
| ephemeral loopback ports (real local servers) | 6 |

**76 connections, 71.5s of connect time, in a 97.99s module -- 73%.** Nothing is
listening on 11434 (verified). 17 of the 21 tests attempt it.

An earlier screen in this campaign reported this same module as opening ZERO
sockets. That screen excluded loopback by design ("reaching the internet is the
question"), and the exclusion hid the single largest cost in the suite. **A
filter chosen to remove noise removed the finding.**

### It is the attempt that costs, not the target

The obvious remedy -- point the endpoint at a closed port, as one test already
does via `override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat")`
-- was measured and **does not work**:

| | runs |
|---|---|
| baseline | 97.85s, 98.61s, **176.75s with 5 failures** |
| endpoint pinned to `127.0.0.1:1` | 102.13s, 105.32s |

Each connect to a closed loopback port costs ~0.94s on this host (71.5s / 76),
whichever port it is. Redirecting the URL changes nothing because the expense is
the connection attempt itself. **Ruled out: fixing this by changing the
configured endpoint.**

(The ~0.94s per refused loopback connect is abnormal -- a closed loopback port
normally answers in microseconds -- so the magnitude is probably specific to
this host's security stack. The DESIGN defect below is independent of that.)

### The defect is that availability is discovered per call

There is no cached availability probe anywhere in `adapters/outbound/llm`.
Nothing asks "is a reader reachable?" once; every path that wants a reader opens
its own socket and finds out. So a machine with no Ollama pays the discovery
cost per document, per test, forever -- and the answer is identical every time.

The fix is a **single probe whose negative result short-circuits every dependent
path**, rather than 17 tests each learning it independently. That is also the
production shape: a real operator without a local model server currently pays
this per document, not once.

### Two smaller defects found alongside

- **The flakiness is real and reproduces**: 5 failed / 176.75s against
  21 passed / ~98s, on identical code. It correlates with the connection
  attempts, and connection-refusal timing is exactly the kind of thing that
  varies run to run. Anything that binds 11434 would change these tests'
  behaviour outright.
- **`cadrumo_llm_ollama_chat_url` is declared in the wrong module.** Every other
  `cadrumo_llm_*` field -- provider, model, API keys, timeouts, retries, cache
  and telemetry dirs -- is declared in `core/_config_llm_fields.py`. The Ollama
  endpoint alone sits in `core/_config_runtime_fields.py:18`. It is a normal
  Settings field with the normal env override; only its home is wrong.

## Fixed: the endpoint is asked once, not once per document

Two commits, driven by the diagnosis above. Both cache the answer to "is the
local model runtime reachable?", which is a property of the machine rather than
of the work, and was being rediscovered constantly at ~0.94s per refused
connection.

**1. `probe_ollama_vision`** now caches its `DependencyStatus` per
`(endpoint, model)` for `OLLAMA_PROBE_CACHE_TTL_S` (10s, matching
`BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS` rather than inventing a cadence).
Keyed on the endpoint, so a suite standing up its own reader on an ephemeral
port asks a different question and is unaffected. Probes fell 65 -> 6.

**2. `_read_runtime_json`** -- found only because the first fix left the module
still slow, and the socket counter was extended to record the CALL SITE of every
connection. That attribution showed **41 of the remaining connections came from
`read_runtime_residents`**, a second endpoint reader with no memory of its own
failures. It now remembers per base URL when the endpoint last refused and
returns the same `None`, without the wait.

**Only failure is cached, and the asymmetry is the design.** A successful read is
answered live every time, so a resident-model set is never stale and contention
is never assessed against a snapshot -- the moment the runtime answers, the cache
stops participating. Only the answer that does not change, and costs most to
obtain, is remembered.

### Measured

| | before | after |
|---|---|---|
| `test_batch_ingest_runner` | 97.85s, 98.61s | **34.30, 34.71, 34.89, 35.61, 35.79s (-65%)** |
| its connections / connect time | 76 / 71.5s | **12 / 8.2s** |
| application integration lane, connect time | 78.6s | **9.2s (-88%)** |
| that lane's wall clock | 211.44s | 205.31s |

The lane wall clock moves only ~6s because it runs six-wide: 69s of saved connect
time divides across workers and the lane is bounded by its slowest one. **The 65%
is what a serial run gets** -- one developer running one file, and every
subprocess CLI invocation.

### Deliberately not done

**No blanket per-test cache clearing.** Caching ACROSS tests is exactly where the
win is; clearing per test would restore the original cost.
`clear_ollama_vision_probe_cache` and `clear_runtime_endpoint_failure_cache` are
exported for a suite that needs a live answer, and the loopback-reader suites
stand up servers on ephemeral ports, so their URLs are distinct keys and they are
safe by construction rather than by luck.

**The TTL was not lengthened** to chase the residual 12 connections. A longer
window trades away the operator-responsiveness the bound exists to protect: a
model server started mid-session must appear without a restart.

### Verification, and two scares that were not the change

- Five consecutive clean runs, 21 passed each.
- A run showing 8 failures occurred only under the socket-counting plugin, which
  patches `socket.connect` and walks the stack on every connection -- intrusive
  enough to trip the module's documented pre-existing flakiness. Four clean runs
  followed without it.
- 96 unit failures across the wider ledger tree are `RegistryValidationError` on
  modelo authority grades: the peer registry campaign, unrelated. Confirmed by
  reading the first failure rather than assuming.
- Both loopback-reader suites, which stand up real servers, stay green
  (34 unit + 3 integration).

### The instrument lesson, twice over

Counting connections found the first caller. It could not have found the second:
after the probe cache landed, the count merely said 40 remained. **Attributing
each connection to its call site is what turned "still slow" into a named
function.** Where a cost survives a fix, instrument WHO pays it, not how much.

## Follow-up: the failure cache verified against the one test that could expose it

The endpoint failure cache remembers "this URL refused" for 10s. The hazard is a
test that stands up a REAL reader at a URL a previous test just recorded as
refusing. Exactly one test in the suite is that shape:
`TestInferencePacing::test_a_document_needing_a_reader_is_read_when_one_is_there`.

Checked directly rather than argued:

| | result |
|---|---|
| the test alone | 1 passed, 4.83s / 4.91s |
| the test after the whole module has cached failures ahead of it | 21 passed, 34.60s / 34.05s |

It is safe because it binds an **ephemeral** port, so its URL is a different
cache key from the default endpoint. That is now confirmed by measurement rather
than inferred from how ports are usually allocated.

## Durations mining is blocked by the red tree in both remaining lanes

Fresh durations at this HEAD:

| lane | result | tail |
|---|---|---|
| `application` (integration) | 118 failed / 285 passed | 42.74s, 38.56s, 28.34s, 26.16s -- **every one a FAILING test** |
| `adapters` (integration) | 105 failed / 113 passed (48% red) | 27.19s + 19.73s in `test_modelo_work_review_screen`, which is 11-failed / 1-passed |

The application tail is entirely `minimo_descendientes` / `guarderia` /
`anualidades` modules failing on `RegistryValidationError`, each paying a full
registry load-and-validate before refusing. **Those timings are the cost of
failing, not the cost of working**, and they will change shape when the registry
campaign lands -- optimising against them would be optimising a program that is
about to stop existing.

This is self-correcting rather than a defect to chase: those tests each
re-validate only because no verdict can be certified while validation fails
(see the verdict-cache section above).

## Ruled out: the login-screen backoff wait

`test_login_screen` is green (8 passed, 22.03s) and its slowest test,
`test_the_operator_can_retry_on_the_same_screen_once_the_backoff_clears`, spends
2.5s in `asyncio.sleep`. A performance pass would reach for the throttle
authority and clear the backoff instead.

**The author already considered and rejected that**, in the constant's own
docstring: the wait is "waited in real time rather than cleared through the
throttle authority: what is being proved is that an operator who mistypes can get
back in on the same screen, and stepping past the control they would actually
meet would prove something weaker."

**Do not re-chase.** The sleep is the test's subject, not its overhead. A
deliberate, documented real-time wait is not a performance defect, and removing
it would trade a proven behaviour for 2.5s.

## Is there a better registry-loading architecture? Yes, and two thirds of it already exists

The pipeline is right; the **phase boundary** is wrong. The architecture rule
already describes it as a compiler: "TOML authoring tree -> loader/compiler ->
strict schema objects -> registry validation -> validated authority". The compile
and validate steps exist -- they just run at RUNTIME, on the operator's machine,
on first use.

### What is already build-time

`dev/packaging/python_cohort.py:_stamp_bundled_verdict_into_build_tree` stamps a
shipped verdict into the build tree, and `_verdict_cache` reads it beside the
installed registry root. Its own docstring states the intent: *"The build and
continuous integration are the validation gate; the runtime asserts fingerprint
identity only."* So **validation (~17.6s) is already a build-time concern** for a
real wheel. That third is done.

### What is not, and the measurement that decides the shape

Two runtime costs remain on every process:

| cost | measured |
|---|---|
| fingerprint walk of 18,847 entries (the cache key) | **0.93s**, every process |
| `_construct_authority` with the compiled artefact present | **2.9s** |
| ...of which reading the 23.0 MB artefact from disk | **0.007s** |

**99.8% of a warm load is rebuilding objects, not I/O.** That single number
changes the answer:

- **Shipping the compiled artefact is necessary but NOT sufficient.** It removes
  the 10.2s first-run compile, and nothing more: every later run still pays the
  2.9s reconstruction. A design that stops at "ship the pickle" fixes the first
  run and leaves the operator-facing number where it is.
- **The lever is not hydrating the whole authority to answer part of a
  question.** `aeat app modelo list` needs ~60 modelo headers and reconstructs an
  object graph compiled from 17,526 fragments.

### The shape this points at

1. **Compile at release, ship the artefact.** Removes the per-machine first-run
   compile entirely. Not as a pickle: pickle executes arbitrary code on load and
   is fragile across interpreter versions, which is the wrong contract for
   something shipped in a wheel. A plain data format -- SQLite is the natural
   fit -- keeps it inspectable and version-stable.
2. **Random access instead of whole-graph hydration.** A single indexed file lets
   a listing surface read the rows it needs and a calculation path read its
   revision, without either paying for the other. This is what makes the
   remaining 2.9s go away rather than move.
3. **Cheap identity for immutable installs.** An installed wheel's registry
   cannot change, so its identity is the package version plus one stamped digest
   -- not a walk of 18,847 entries per process. Keep the full walk for editable
   and authoring trees, where files genuinely do change; that distinction already
   exists (`is_bundled_registry_root`, and the separate fingerprint TTLs).

### Why this is better architecture, not just faster

It resolves a tension already recorded in this audit. The earlier remedy for CLI
load time was "a metadata projection for listing surfaces", which
`aeat-registry-authority-flow` resists for good reason: it forbids parallel read
paths over registry data, because snapshot construction is authority-owned.
Random access over ONE shipped artefact is not a second read path -- it is the
same authority, consulted without being fully hydrated first. **The projection
idea and the no-parallel-paths rule stop conflicting.**

It also puts the compiler where the rule already says it belongs, and makes the
runtime do what that docstring already claims it does: assert identity, not
recompute the answer.

### Cost, honestly

This is a release-pipeline and artefact-format change touching the registry
authority -- the most load-bearing surface in the application. It is an ADR, not
a sweep. The prize, from the numbers above: a warm authority load of ~3.8s
(0.93s identity + 2.9s hydration) becomes a read plus a partial hydration, and
the 33s cold CLI loses its compile entirely.

## The combined-period gate: measured, three levers tried, none shipped

`core/tests/test_period_combined_string_gate.py::test_repo_has_no_unallowlisted_combined_period_strings`
is the slowest test in the largely-green unit lane (3,856 passed / 50 failed in
160.31s) at **25.21s**. Phase split, repeated twice and stable:

| phase | seconds | share |
|---|---|---|
| git index parse (no subprocess -- already efficient) | 0.035 | -- |
| enumeration incl. a `Path.is_file()` per candidate | 2.9 | 13.5% |
| read + decode 403.1 MB across 26,824 files | 3.6-3.8 | 17% |
| **regex, 2 whole-text patterns** | **14.5-15.0** | **69.7%** |

### Ruled out: merging the two whole-text patterns into one alternation

Both patterns share the century prefix `(?:19|20|21|22)\d{2}` and differ only in
their tail (`Q[1-4]` versus `-[1-4]T`), so the corpus is walked twice to find the
same prefix. Merging them looked free.

Equivalence was proven first -- the alternation built AUTOMATICALLY from the
declared patterns as `(?P<p0>...)|(?P<p1>...)`, so it cannot drift from them --
and compared as finding sets over every file: **0 mismatching files of 26,824,
530 findings both ways.**

It is **slower**: 20.974s against 15.078s.

Python's `re` extracts a literal-prefix scan from each standalone pattern; a
top-level alternation destroys that and tries both branches at each position.
**Do not merge these patterns.** More generally: **restructuring a regex to
"share work" can remove an optimisation the engine was already applying.**

### Ruled out: memoising the corpus enumeration

`_tracked_text_files()` is called by both tests in the module and costs 2.9s
standalone, so `@cache` looked like a free 2.9s. Measured: **26.62s median of
three (25.72-30.30) against a 25.21s baseline -- no win**, because the second
call is already cheap in-test (module total ~26s, main test ~25s, so the second
test's whole share is ~1s). **Reverted rather than kept**: a semantically safe
change with no demonstrated benefit is still an unjustified change.

### Not taken unilaterally: the scan corpus is 74% third-party document text

| tree | bytes | share |
|---|---|---|
| `_data/corpus` (bundled BOE/AEAT documents) | 239.2 MB | **62.8%** |
| `_data/manual_corpus_text` | 43.0 MB | **11.3%** |
| `_data/registry` | 28.8 MB | 7.6% |
| all first-party source under `src/cadrumo` | the remaining ~18% | |

The gate exists to stop THIS REPO writing combined period strings. A combined
period string inside bundled BOE text is AEAT's wording, is byte-exact evidence,
and could not be fixed if found -- and the allowlist already excuses that class
("external HTML/PDF corpus and fixture generation material preserves
official/source labels"). Excluding `_data/corpus` and `_data/manual_corpus_text`
would cut ~282 MB of the 403 MB scanned, taking the regex phase from ~15s to
~4.5s and the read from ~3.7s to ~1.1s: **25.21s -> roughly 7s.**

**This is a gate-scope narrowing and is left as an owner decision.** What it would
exclude, stated plainly as the rule requires: the gate would no longer notice a
combined period string appearing in bundled corpus text. That is judged
unactionable rather than harmless -- the files are external evidence -- but it is
a real reduction in what the gate sees, and the module already carries an
anti-vacuity floor (`len(corpus) > 500`) precisely because someone worried about
this corpus collapsing.

**Four consecutive levers on this file measured no better or worse than the
baseline.** The remaining one that would work is the scope decision, not a
technique.

## The unit-lane tail decomposes into three classes, and none is an unexploited lever

Sampled the top of the largely-green `core` + `persistence` unit lane
(3,856 passed / 50 failed, 160.31s). Every entry falls into one of three
buckets:

**1. The registry authority load -- already decomposed and handed off.**

| test | sampled self time |
|---|---|
| `topics/tests/test_catalogue.py::test_every_topic_legal_ref_resolves_against_real_legal_catalogue` (20.67s) | `open` 21.3%, `realpath` 19.2%, `read_text` 13.6%, `stat` 10.9%, `_read_entries` 9.8%, bs4 5.2% |
| `profile/tests/test_calculation_repository_roundtrip.py` (34.49s) | `open` 17.6%, `realpath` 16.6%, `stat` 11.7%, `read_text` 8.9% |

That is the same filesystem-dominated authority load measured earlier
(0.93s fingerprint + 10.2s cold compile + validation), and both modules are
additionally registry-red. **Nothing new to do here**: the lever is the
build-time-compiled, randomly-accessible artefact recorded in the architecture
section, not anything per-module.

**2. Deliberate real-process and real-time waits -- the subject, not overhead.**

`custody/tests/test_kdf_supervision.py` (17 passed, 25.16s) is **88.7% in
`threading.wait`**, waiting on real supervised Argon2 subprocesses: lease
blocking, process death, recovery. Removing the waits would remove what the
module proves. Same shape as the login-screen backoff ruled out above.
**Do not "optimise" a test whose subject is a real wait.**

**3. Contention artefacts -- targets that are not slow.**

`bucket/tests/test_trash_rename_and_remove.py` was listed at **15.41s** in the
parallel lane run and measures **1.42s** in isolation: a **10.8x inflation**. Its
sampled profile is 56% import machinery -- there is no test cost to remove.

This is the recorded hazard made concrete: **durations under `-n auto` are work
PLUS contention.** Any candidate taken from a parallel run must be re-timed in
isolation before it is believed, or the work goes to a module that was never
slow.

### Where that leaves the loop

Across the CLI lane, the application lane, the adapters lane and now the unit
lane, the tail is fully accounted for by: the registry authority load (handed
off as an architecture change), deliberate waits, error paths from the in-flight
registry campaign, and contention inflation. **No unexploited per-module lever
was found in this pass.**

The remaining named opportunities are all decisions rather than techniques:
the compiled-artefact architecture, the combined-period gate's scan scope, and
the worker-count cap. Further per-module profiling on this tree is unlikely to
return until the registry campaign lands and the tail can be re-measured green.

# Campaign close

## What landed, with its measurement

| change | effect |
|---|---|
| xdist fail-closed policy (`--max-worker-restart=0`) + a gate proving it | worker death now aborts loudly instead of deadlocking or corrupting a run |
| explicit timeouts on the two 8-wide subprocess-pool gates and the real double-build | a hung pool is bounded rather than silent |
| KDF calibration measurement declined across three doors | profile registration 17.44s -> 2.20s |
| locale honesty gate: `@cache` + `CSafeLoader` | 125.14s -> 6.04s |
| import-hygiene scan memoised (reused by the edge-integrity gate) | 249s -> 108s |
| `dev/locales` C loader | 282s -> 137s |
| MCP tool descriptors memoised | harness slice 143s -> 93s |
| packaging cohort wheels built once per module | 204s -> 153s |
| ledger list-filter: parse refusals de-corpused, world seeded per file | 91.30s -> 53.9s (median of 3) |
| asesor / yearend / multicurrency personas: seed-once, copy-per-test | seedings 10/9/7 per module -> 1 each |
| header-cell fold: one `translate` pass, memoised | 2.50x on the function; byte-identical across 5,527 inputs |
| registry directory validators return what they classified | 115 fewer listings per compile |
| **`probe_ollama_vision` + `_read_runtime_json` endpoint caches** | **`test_batch_ingest_runner` 98s -> 35s (-65%)**; application-lane connect time 78.6s -> 9.2s |

## What is open, and it is decisions rather than techniques

- **Compiled-registry artefact** -- the largest remaining lever. Handed off as a
  copy-paste brief: hash once, compiled DB, drift detection, rebuild on
  mismatch. The deciding measurement is in this audit: reading the 23.0 MB
  artefact is 0.007s against a 2.9s warm load, so shipping it is necessary but
  not sufficient -- the artefact must be randomly accessible.
- **Combined-period gate scan scope** -- 74% of its 403 MB is bundled
  third-party corpus text. Excluding it is ~25s -> ~7s and narrows what the gate
  sees; stated with the exclusion named.
- **`DEFAULT_WORKER_COUNT`** -- the only remaining wall-clock lever, costed at
  ~1.7 GB session state per worker plus ~0.33 MB/test, peaking 4-5.7 GB.
- **`cadrumo_llm_ollama_chat_url`** sits in `_config_runtime_fields.py` while
  every other `cadrumo_llm_*` field lives in `_config_llm_fields.py`.

## The honest part

Four ideas were implemented, measured, and **not shipped** because they were no
better or worse: the alternation regex merge (20.97s vs 15.08s), the corpus
enumeration memo (reverted), hand-rolling the TOML read (0.87x/0.83x), and the
section-directory scan fold (32% fewer listings, slower). Two headline claims
were **corrected after the fact**: the ECB "47% of a test" (really 1-2% of the
lane) and cProfile's attribution of ~30s to a string helper (really 1.4%).

Three instrument failures cost the most time and are recorded as standing
lessons: **cProfile measures the profiler** on call-count-heavy code; **a reduced
call count is not a reduced cost**; and **a filter chosen to remove noise removed
the finding** -- excluding loopback hid the largest cost in the suite until
call-site attribution found it.

## Not yet done: the closure honesty review

`aeat-agent-orchestration` requires a fresh-context honesty review against this
closure summary before structural completeness may be declared. **That review has
not been run**, so this section is a closure summary and not a completeness
claim. Its first question should be whether the ruled-out levers above were ruled
out on measurement or on fatigue.

# Closure honesty review

Run against the closure summary above, as `aeat-agent-orchestration` requires.
Its nominated first question was whether the rule-outs were measured or fatigued.
Two findings, and the second is the campaign's own documented error committed by
its own author.

## Finding 1: the headline number is overstated

Claimed: `test_batch_ingest_runner` **98s -> 35s (-65%)**.

Re-measured at HEAD `30cb295f31`, three runs: **43.85s, 38.87s, 42.86s** --
median **42.86s**, all 21 passed. Against the ~98s before-state that is
**-56%, not -65%**.

All six landed changes are verified present at HEAD, so this is not a revert. The
34.30-35.79s five-run set that produced the -65% claim was taken in one session
and is not reproducing; the machine or the tree has moved under it.

**Corrected claim: ~98s -> ~39-44s, about -56%.** The structural half of the
claim is unaffected and remains reproducible: connections 76 -> 12, connect time
71.5s -> 8.2s.

**Lesson repeated from earlier in this same audit:** a multi-run median taken in
one sitting is still one sample of the machine. The FX deltas were withdrawn for
exactly this and the headline was not re-checked against a later day.

## Finding 2: a rule-out was decided on an invalid comparison

The corpus-enumeration memo on the combined-period gate was reverted because it
measured **26.62s median against a 25.21s baseline**.

That baseline was wrong. **25.21s came from a `-n auto` LANE run; the 26.62s came
from isolated `-n0` runs.** The isolated baseline, measured now over three runs,
is **26.56s, 28.24s, 27.10s -- median 27.10s**.

So the memo was **marginally faster** than its true baseline (26.62s vs 27.10s),
not slower. The revert still stands on its merits -- ~0.5s against a 1.7s
run-to-run spread is below noise, and an unjustified change is still unjustified
-- but **the stated reason was false**, and the correct reason is "no measurable
win against a properly matched baseline".

This is precisely the hazard this audit documented two sections earlier, with a
measured 10.8x contention-inflation example, and then repeated. **A parallel-lane
duration and an isolated duration are not comparable numbers.** Any before/after
must hold the execution mode fixed.

## Rule-outs re-examined: which were measured, which were judged

| rule-out | basis | holds? |
|---|---|---|
| alternation regex merge | 20.97s vs 15.08s, equivalence proven over 26,824 files | measured, solid |
| hand-rolled TOML read | 0.87x / 0.83x, 3,000 files, 5 repeats, equality gate | measured, solid |
| section-directory scan fold | 1.49s vs 1.29s, five runs each, same mode | measured, solid |
| directory-scan dedup ceiling (0.26s) | time inside `_read_entries`, three runs | measured, solid |
| registry disk cache relocation | before/after on two modules, three runs each | measured, solid |
| six read-only module conversions | all six timed | measured, solid |
| corpus enumeration memo | **invalid baseline** -- see Finding 2 | reason corrected |
| bs4 -> lxml | **not measured**; declined on risk/reward | judgement, labelled as such |
| login-screen backoff wait | documented author intent | correct basis, not a timing question |
| seeding tail (~1%) | seed costs measured, aggregate reasoned | part measured, part estimated |

Eight of ten were measured. One was a judgement call and is labelled as one. One
was decided on a bad comparison and is corrected here. **No rule-out was found to
be fatigue presented as evidence** -- but one was evidence read carelessly, which
is the same outcome from a different cause.

## Verdict

The campaign's landed work is verified present and its structural claims hold.
One headline figure is corrected downward, and one rule-out's reasoning is
corrected while its conclusion survives. **Structural completeness may be
declared for the landed work**; the open items in the closure summary remain
open and are decisions, not omissions.
