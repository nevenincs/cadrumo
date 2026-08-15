---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:20b2ab4ce654bb29392b634e3971e96d3f188d82accbbecb97a8994a9f716743'
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
