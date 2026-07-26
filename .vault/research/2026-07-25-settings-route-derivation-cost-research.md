---
tags:
  - '#research'
  - '#settings-route-derivation-cost'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-05-ledger-latency-budget-adr]]"
---

# `settings-route-derivation-cost` research: `Per-handle Settings re-derivation cost on the repository-handle path`

Every repository handle in the application re-derives a whole `Settings` instance. Acquiring a
bucket-scoped repository calls `settings_for_bucket_route`
(`src/cadrumo/core/_config_storage_route.py:76`), which dumps the source settings to a dict and
re-validates the entire model, re-running every field validator and the after-validator that
touches disk. The question this research grounds: how large is that cost really, and what would a
cached derivation have to preserve to stay correct?

The cost is real but roughly a sixth of the figure previously circulated. The headline "69% of
runtime" attributed to this path in the issue #607 thread is a cProfile artefact; measured without
a profiler the derivation is ~11% of a Modelo 130 calculate quarter. A second, previously
unrecorded effect works the other way: the benchmark harness structurally cannot see roughly half
the production cost, so the true production figure is about double what any current gate measures.

The re-derivation is deliberate machinery, not an oversight, so the option space is not
"remove it" but "derive once and reuse within a scope that preserves what the derivation
guarantees". What that scope must be is the open question for the ADR.

## Findings

### The re-derivation exists to re-derive a computed field, and cannot be replaced by `model_copy`

`cadrumo_database_url` is a derived field, not an input. `settings_for_bucket_route` drops it,
sets `cadrumo_active_profile` to the target bucket, and re-validates so the model's own validators
recompute the URL (`src/cadrumo/core/_config_storage_route.py:100-103`). It then restores
`__pydantic_fields_set__` so the derived instance still reports which fields the operator set
explicitly, which route classification depends on.

`model_copy(update=...)` is not an available shortcut, and the codebase already knows why: the
sibling `override_settings` helper carries the comment that `model_copy(update=)` skips validators
in Pydantic v2 and therefore routes its merged dict through `model_validate` instead
(`src/cadrumo/core/config.py:1367` and following). Any proposal that reuses a `Settings` instance
without re-running validation inherits that hazard.

So the derivation's *purpose* is sound. What is questionable is its *repetition*: nothing about the
source settings changes between handles within one calculation.

### The re-validation redoes filesystem work that is invariant across handles

Two classes of disk-touching work run on every derivation:

Around thirty optional path fields each pass through the `_normalize_repo_relative_paths` field
validator (`src/cadrumo/core/config.py:1286`), which delegates to `normalize_project_relative_path`
and ultimately `resolve_project_path` — a `Path.resolve()`, and therefore a filesystem syscall per
field. On Windows these surface as `nt._getfinalpathname`.

The after-validator that derives the database URL calls `refuse_former_product_database`
(`src/cadrumo/core/config.py:1094` and `:1102`), a safety refusal that inspects the storage root.
Because `settings_for_bucket_route` sets `cadrumo_active_profile` explicitly, the pointer-file read
branch above it is skipped and only the bucket-scoped refusal runs.

Neither depends on which handle is being acquired. For a fixed storage root and bucket id both are
invariant, which is what makes this hoistable rather than merely cacheable.

Counted per four Modelo 130 quarters, undistorted by profiler: 56 calls to
`secure_object_repository_for_bucket` (36 of them originating in
`UserProfileLifecycleRepository._secure_objects_for_bucket` alone), 112 `Settings` constructions,
3,584 `_normalize_repo_relative_paths` invocations, 13,440 `nt._getfinalpathname` and 3,528
`nt.readlink` syscalls.

### The "69% of runtime" figure is a cProfile artefact; the measured share is ~11%

The issue #607 thread recorded `secure_object_repository_for_bucket` at 69% of profiled time. The
wording was literally accurate and the call counts above corroborate its structural claim, but the
share does not transfer to wall-clock. cProfile overhead on this path is roughly tenfold — the same
quarter measured 70.3 s profiled against 7.4 s unprofiled — and it inflates pure-Python frames
while collapsing Rust `pydantic-core` validation into single C calls. `Settings` validation is
pure Python; row validation is Rust. The instrument therefore over-attributes to precisely the
component under examination.

Measured without a profiler, n=200:

| call | mean | median |
| --- | --- | --- |
| `settings_for_active_profile_bucket` | 13.4 ms | 12.9 ms |
| `Settings.model_dump` | 0.063 ms | 0.065 ms |
| `load_settings()` with no override installed | 21.8 ms | 13.7 ms |

Fourteen handles per quarter at 13.4 ms is approximately 188 ms per quarter, against a recorded
mean quarter of 1.737 s — about 11%. `model_dump` is negligible at 0.5% of the derivation, so the
cost is entirely `Settings.model_validate`, which locates the lever precisely.

A claim of "the single largest quantified inefficiency in the codebase" is not supportable at this
size. The lever remains worth taking; it should be justified at its measured size.

### The benchmark structurally under-measures the production cost by roughly half

`load_settings()` returns the context-local override when one is installed and otherwise constructs
a fresh `Settings()` on every call (`src/cadrumo/core/config.py:1353`). There is no cache on that
path. `settings_for_active_profile_bucket` defaults its source to `load_settings()`
(`src/cadrumo/core/config.py:1339`), and `_secure_objects_for_bucket` calls
`secure_object_repository_for_bucket(bucket_id, load_settings())`.

The scale benchmark runs under an isolated runtime profile, hence inside `override_settings`, where
`load_settings()` is a cached attribute read. Production installs no override, so every handle
additionally pays a full `Settings()` construction — measured at 21.8 ms mean.

Production per-handle cost is therefore approximately 27 ms rather than 13 ms, putting the true
figure near 380 ms per quarter against the ~188 ms any current harness can observe. This is
load-robust: it follows from the absence of a cache on a code path, not from a timing.

It also means no benchmark-gated verification of a fix will show the full improvement, which the
ADR should account for when choosing its evidence.

### What a cached derivation must preserve

Three hazards constrain the option space.

Context-local override isolation. `_settings_override` is a `contextvars.ContextVar`
(`src/cadrumo/core/config.py:1291`) and `suppress_operator_dotenv` is a second one. A
process-global cache keyed on bucket id alone would serve an instance derived outside an override
scope to a caller inside one, breaking test isolation and defeating the sandbox seam that exists to
keep operator machine state out of hermetic runs.

Unstable cache keys in production. Because `load_settings()` returns a fresh object per call when
no override is installed, a cache keyed on source-instance identity would never hit in production
while hitting reliably under test — the same asymmetry that hid the cost above, inverted into a
correctness-of-measurement problem.

Filesystem-derived state. The derivation re-runs `refuse_former_product_database` and re-resolves
paths. A cache is a decision that this state is stable for the cache's lifetime. Within one
calculation that is defensible; process-wide it asserts something much stronger. The registry
authority already governs this class of mistake: `aeat-registry-authority-flow` requires cache
invalidation on a complete tree fingerprint and explicitly forbids path-only keys that can serve
stale state after source edits.

### Prior art in-tree favours a calculation-scoped read-through wrapper

`MemoizedTransactionCatalogueRepository` (`src/cadrumo/application/modelo/_transaction_catalogue_cache.py`)
solves the shape of this problem for catalogue reads: a wrapper that memoises immutable reads for
the duration of one source-mesh calculation while delegating writes straight through to the
authority repository. Its scope is the calculation, not the process, so it never has to answer when
to invalidate — the object's lifetime is the invalidation.

The same shape applied to repository *handles* would collapse the fourteen derivations per quarter
toward one, and sidesteps all three hazards above by construction rather than by policy. Naming it
here is scoping evidence, not a decision; whether the scope should be the calculation, the bucket,
the route, or the process is what the ADR must settle, along with where the wrapper is installed so
that callers outside the calculate path also benefit.

The caller set is small enough to make any of those tractable: `settings_for_bucket_route` has one
production caller, the `settings_for_active_profile_bucket` facade
(`src/cadrumo/core/config.py:1350`), which in turn is reached from
`src/cadrumo/adapters/persistence/storage/runtime.py:405`,
`src/cadrumo/application/storage_write_policy.py:316`, and
`src/cadrumo/domain/usage_ratios/_service.py:72`.

### Recorded trap: the full-scan catalogue read is not on the Modelo 130 path

`TransactionCatalogueRepository.load()` is not called during a Modelo 130 calculate. The M130
cumulative window reads through `partition_by_date_range`
(`src/cadrumo/application/aggregation/_renta_income_ledger.py:204`); the `load()` at
`:303` belongs to the Modelo 100 annual branch.

This is recorded because it has already cost real effort twice. Issue #607 names its lever as
"per-row validation on the load path", and the obvious reading of that phrase points at `load()` —
an operation this path no longer performs. Anyone optimising it would measure no improvement and
conclude the analysis was wrong rather than the target.

### Parked per-row items, two of which are not defects

Three per-row redundancies were circulated alongside this work. They are recorded here with
corrections because two of them are load-bearing correctness machinery and actioning them as
described would weaken validation.

Identity re-derivation on already-validated frozen instances (~22 µs/row) is genuine and
unactioned. It sits on the `load()` path, so it does not affect Modelo 130.

The claim that a D6 timestamp guard performs a second full `json.loads` while its docstring falsely
claims a shared parse is **false at HEAD, and inverted**. `json.loads` appears exactly once in
`src/cadrumo/adapters/persistence/profile/transactions.py:151`; the row decode at `:285` produces a
dict the guard then consumes. The docstring is accurate.

The companion claim that `Envelope[T]` "degrades inner payload validation to python mode" is
likewise backwards. The envelope deliberately re-reads the original bytes via
`model_validate_json` because JSON mode is *required* for correct string-to-datetime and
string-to-enum coercion under its `strict=True` config; `model_validate` over the already-decoded
dict runs in python mode and rejects those coercions outright. The second parse is the correctness
mechanism, not waste. The code documents this inline.

### Not investigated

Whether the syscall counts hold off Windows. `nt._getfinalpathname` is Windows-specific, though
`Path.resolve()` issues syscalls on every platform, so the shape should transfer while the
magnitude may not.

Whether a fix is verifiable by the existing harness. Following from the under-measurement finding
above, roughly half the production win is invisible to a benchmark running under
`override_settings`; no alternative measurement strategy was designed here.

An unexplained observation, flagged rather than claimed: one profiled round attributed 117.9 s
across 20 `_io.TextIOWrapper.flush` calls. It was originally reported as reaching those flushes via
a `logging.debug` call in the work-unit repository, but that attribution does not survive checking
— the module has no logging call anywhere in its 207 lines, and the cited line is a method
definition. The caller is therefore unidentified. Unprofiled quarters completed in 5.9–8.6 s in
total, so this cannot be a stable property and is most likely IO contention on a saturated host. It
is not part of this cost picture and would need isolating on a quiet machine before it is worth
attributing to anything.

No wall-clock verdict is offered for any operation here. Every timing in this document is a
per-call microbenchmark or a ratio; the host carried 262–385 concurrent Python processes at
97–100% CPU across 24 logical cores throughout, which makes end-to-end wall-clock unusable and is
why the structural and per-call figures were gathered instead.

## Sources

`src/cadrumo/core/_config_storage_route.py:76`, `:100-103` — the derivation under examination.

`src/cadrumo/core/config.py:1094`, `:1102` — `refuse_former_product_database` inside the
URL-deriving after-validator.

`src/cadrumo/core/config.py:1286` — `_normalize_repo_relative_paths` field validator.

`src/cadrumo/core/config.py:1291` — `_settings_override` context variable.

`src/cadrumo/core/config.py:1339`, `:1350`, `:1353`, `:1367` — the bucket facade, its delegation,
uncached `load_settings`, and the `override_settings` comment rejecting `model_copy(update=)`.

`src/cadrumo/adapters/persistence/storage/runtime.py:405`,
`src/cadrumo/application/storage_write_policy.py:316`,
`src/cadrumo/domain/usage_ratios/_service.py:72` — the production caller set.

`src/cadrumo/application/modelo/_transaction_catalogue_cache.py` — calculation-scoped read-through
memoisation prior art.

`src/cadrumo/application/aggregation/_renta_income_ledger.py:204`, `:303` — the M130 partition read
and the M100 annual `load()`.

`src/cadrumo/adapters/persistence/profile/transactions.py:151`, `:285` — single JSON decode and the
guard that consumes it.

`src/cadrumo/application/aggregation/tests/test_ledger_scale_benchmark.py` — the harness whose
`override_settings` isolation causes the production under-measurement.

Call counts, per-call microbenchmarks (n=200), and the profiled-versus-unprofiled ratio were
gathered on 2026-07-25 against HEAD `3d5aa40f78` under the recorded host load; they are
reproducible in shape but not in absolute value on a loaded machine.
