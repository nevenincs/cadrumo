---
tags:
  - '#adr'
  - '#registry-disk-cache-pytest'
date: '2026-07-07'
modified: '2026-07-08'
related: []
---

# `registry-disk-cache-pytest` adr: `enable the registry disk cache under pytest for the bundled root only` | (**status:** `accepted`)

## Problem Statement

Loading the full AEAT registry (`load_registry_tree`) compiles and validates
every `legal/*.toml`, `modelos/*.toml`, and directory/fragment-mode modelo
source under the registry root. A true cold compile of the bundled tree costs
several seconds to over ten seconds depending on machine load (measured 7.5s
to 8.4s on a lightly loaded machine in this session; the operator's own
measurement under heavier concurrent load was 14.45s). A prior fix (issue
`#44`) found that the loader's cross-process `/tmp` disk pickle -- keyed by a
SHA-256 of `(schema_version, root, per-file path/size/mtime)` -- was shared
across pytest-xdist worker processes, and a parallel `-n` run could serve a
stale or transiently-inconsistent compiled registry from one worker to
another when the underlying root was a synthetic `tmp_path` tree a test was
actively mutating (the M303-2009 ledger flake). The `#44` fix closed the race
by disabling the disk pickle unconditionally under pytest (`"pytest" in
sys.modules`, or any of the `PYTEST_CURRENT_TEST` / `PYTEST_XDIST_WORKER` /
`PYTEST_VERSION` env markers).

That fix over-corrected: it disabled the disk cache for EVERY registry root
under pytest, not only the mutable/synthetic roots the race actually concerns.
Every pytest-xdist worker, and every subprocess-spawning test that boots a
fresh interpreter, therefore independently recompiles the bundled,
package-shipped registry tree from scratch -- the single largest per-process
fixed cost in the test suite, paid N times over across a parallel run and
paid again by every cold-boot subprocess test (the acceptance-wall gate,
cold-start CLI tests, and similar).

## Considerations

- The bundled registry tree (`is_bundled_registry_root`) is shipped inside the
  installed wheel or force-included from the in-tree `registry/aeat` directory
  under an editable install; it is never mutated by test code during a run.
  Concurrent peer agents in this shared worktree DO edit it live across a
  session, but never mid-single-test-run in a way the `#44` race concerns
  (that race is about a test building and then immediately reloading its OWN
  synthetic tree while a sibling worker's stale pickle races it).
- The `#44` race is specifically about a MUTABLE root: a `tmp_path` synthetic
  registry a single test constructs, edits, and reloads within its own body,
  where the mtime-keyed pickle could theoretically be shared with (or served
  from) a different worker mid-construction.
- The disk-cache key already includes a fingerprint of the resolved root path
  plus a `(path, size, mtime)` triple per file; content that has not changed
  produces the identical key deterministically across processes, which is
  exactly the property that makes safe cross-process sharing possible for an
  immutable tree.
- `is_bundled_registry_root` already exists and is already used to select the
  longer fingerprint TTL for the bundled tree (`BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS`
  vs `MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS`); this ADR reuses the same
  predicate for the disk-cache gate rather than introducing a second
  root-classification mechanism.

## Considered options

- **A -- Enable the disk cache under pytest for the bundled root only
  (chosen).** Thread the already-computed `is_bundled_registry_root(resolved)`
  boolean into `registry_disk_cache_enabled(is_bundled=...)`; keep the boolean
  default (`False`) fail-closed to the strict/no-cache behavior for any
  caller that does not explicitly pass it. Preserves the `#44` invariant
  byte-for-byte for every mutable/synthetic root while unlocking sharing for
  the one root class that is provably immutable during a run.
- **B -- Harden the disk-cache key to a full content hash (e.g. read and hash
  every TOML file's bytes) before enabling any pytest sharing.** Rejected as
  the default for this fix: the bundled root's immutability during a run is
  already the safety argument, not the key's collision resistance; hashing
  every file's bytes on every fingerprint computation adds I/O the size/mtime
  fingerprint avoids, partially offsetting the win this ADR exists to capture.
  Left as a documented future hardening if a corruption/tamper scenario ever
  motivates it, not required for this decision.
- **C -- Give the bundled root a process-lifetime (never-expiring) in-memory
  cache instead of a disk cache, skipping the pickle entirely.** Rejected:
  this only helps a single long-lived worker process reuse its own compile: it
  does nothing for the cross-process case (a fresh subprocess-spawning cold-
  start test, or a fresh xdist worker) which is exactly where the biggest cost
  is paid today. The disk pickle is the only mechanism that survives a process
  boundary.
- **D -- Leave the `#44` fix as-is and instead batch/reduce the NUMBER of
  cold boots (a separate, complementary fix already tracked elsewhere in this
  campaign).** Rejected as a substitute here (though pursued in parallel as a
  distinct fix): it reduces N but does not remove the per-boot cost this ADR
  addresses, and does not help the pytest-xdist worker-count case at all.

## Constraints

- The fix must not weaken the `#44` isolation guarantee for any root that is
  not the resolved bundled path; the existing `test_loader_cache_isolation.py`
  invariant (disabled for a mutable/default root) must continue to pass
  unchanged.
- The gate function's existing callers (a production script with no pytest
  markers at all) must keep behaving identically: unconditionally enabled
  outside pytest, regardless of the `is_bundled` argument.
- No change to the pickle payload SHAPE (`(modelos, catalogues)`) or to the
  `_REGISTRY_TREE_CACHE_SCHEMA_VERSION` constant is needed; only the gating
  predicate changes.

## Implementation

`registry_disk_cache_enabled` (`_loader_cache.py`) gains an `is_bundled: bool = False`
keyword-only parameter. Its pytest-detection logic (the `"pytest" in
sys.modules` check plus the three `PYTEST_*` env-marker checks) is collapsed
into a single `under_pytest` boolean, computed exactly as before (any one
signal is sufficient). When `under_pytest` is true, the function now returns
`is_bundled` directly instead of an unconditional `False`; when false
(production, no pytest signal at all), it returns `True` regardless of
`is_bundled`, preserving the existing production behavior exactly.

`_load_registry_tree_cached` (`_loader.py`) computes `resolved = Path(root)`
before the disk-cache gate (previously computed after) and passes
`is_bundled_registry_root(resolved)` into `registry_disk_cache_enabled`. This
reuses the predicate already imported into `_loader.py` for the TTL decision;
no new import or root-classification path is introduced. Every other branch
of the read/write disk-cache logic (the SHA-256 key construction, the
atomic write via a temp file plus `os.replace`, the broad-exception
swallow-and-recompute on a corrupt/foreign file) is unchanged.

## Rationale

The bundled tree is the one registry root every test-suite run and every
production boot shares byte-for-byte and never mutates mid-run; sharing its
compiled disk pickle across pytest-xdist workers and cold-boot subprocesses is
safe for the same reason production has always kept the cache on: no
concurrent writer. Scoping the re-enable to exactly that root, via the
predicate the codebase already trusts for the TTL decision, closes the
performance regression the `#44` fix introduced as a side effect while
leaving the `#44` safety property completely intact for the only root class
it was ever protecting.

Measured in this session (bundled tree, ~73 modelos, lightly-loaded machine):
a first (pytest-marked) process compiling the bundled tree cold and writing
the shared disk pickle took 8.23s; a second, independent process (fresh
interpreter, fresh in-process `lru_cache`, same `PYTEST_CURRENT_TEST` marker)
reading that shared pickle took 1.02s and 1.04s across two repeated runs --
an approximately 8x reduction per worker/subprocess after the first compile,
matching the ~8x production disk-cache win already observed outside pytest
(8.41s cold vs 1.04s warm). Under the prior `#44` behavior, every one of those
processes would have independently paid the full 7.5s-16s cold cost with zero
sharing.

## Consequences

- Every pytest-xdist worker beyond the first to touch the bundled registry
  root, and every subprocess-spawning cold-boot test (the acceptance-wall
  gate, cold-start CLI tests), now pays a disk-pickle read (roughly 1s) instead
  of a full cold compile (roughly 8-16s depending on load) after the first
  compile in the run has written the shared pickle.
- The `#44` safety property is unchanged for every mutable/synthetic root: a
  test's own `tmp_path` registry never touches the disk cache under pytest,
  proven by a new real-behavior test that builds one and asserts no pickle is
  written.
- A new real-behavior test (`test_bundled_root_disk_cache_is_shared_across_processes`)
  proves the cross-process sharing end-to-end through the actual
  `load_registry_tree` entry point and the actual `/tmp` pickle file (byte-
  identical mtime and size after a second process reads it), not merely
  through the boolean gate.
- A stale bundled-root pickle from a version of this codebase prior to this
  fix, or from a differently-configured checkout, self-heals: the SHA-256 key
  already covers `schema_version` plus every file's path/size/mtime, so any
  content drift produces a different key and the loader recompiles rather
  than serving a mismatched payload.
- Left open per the rejected option B: if a future incident ever suggests the
  size/mtime fingerprint is an insufficient collision guard for the bundled
  root specifically, hardening the key to a full content hash is a
  self-contained follow-up that does not require revisiting this decision's
  root-classification approach.

## Amendment: the session-isolation fixture defeated the gate it was measured against

A subsequent re-grounding of this decision (before the reviewer gate) found the
gate change above, while correct, was NOT delivering its measured win in a real
multi-worker run: `src/aeat/conftest.py`'s `_isolate_registry_caches` fixture is
`scope="session", autouse=True` and unconditionally purged EVERY
`aeat_registry_*.pkl` at session start. Under pytest-xdist, `scope="session"`
means "per worker process" -- there is no single controlling session spanning
all workers -- so every worker's own session start deleted the very pickle a
sibling worker (or an earlier invocation) had just written, forcing every
worker to independently recompile the bundled tree from scratch with zero
sharing. This fixture predates the gate change above and was written when the
disk cache was UNCONDITIONALLY disabled under pytest (so any pre-existing
pickle could only have come from a prior non-pytest run); it was never updated
when the gate above started writing to disk under pytest for the bundled root.

Measured directly: two separate real `pytest` invocations against the same
throwaway test module (each its own "session," exactly the same fixture-scope
boundary a real xdist worker's own session is) touching the bundled registry,
BEFORE removing the purge: 1st invocation 8.7s (cold, writes the pickle), 2nd
invocation ALSO recompiled (mtime changed, confirming the purge deleted the
1st invocation's pickle before the 2nd invocation's own test ran). AFTER
removing the purge (the fix below): 1st invocation 8.9s, 2nd invocation 1.3s,
3rd invocation 1.3s, pickle mtime and size unchanged across all three.

**Fix:** `_isolate_registry_caches`'s `_reset()` helper no longer purges the
disk cache at session start (or end -- session end never purged it either).
It now only clears the in-process `lru_cache` and the 1-second-TTL fingerprint
cache, which is process-local and cheap and was never the problem. The
disk-cache read path is already self-validating (the SHA-256 covers the schema
version plus every file's path/size/mtime), so a stale or incompatible pickle
simply misses its own key and gets recompiled+rewritten -- the defensive purge
provided no correctness guarantee the key itself does not already provide, only
a false sense of "tidiness" that actively worked against this ADR's decision.

A new regression test
(`test_bundled_root_disk_cache_survives_across_separate_real_pytest_sessions`)
materialises a pid-suffixed throwaway sibling test module in the real registry
`tests/` directory and runs it through TWO REAL, SEPARATE `pytest` subprocess
invocations (not simulated via env vars), asserting the bundled disk pickle's
mtime and size are unchanged across both -- proven to fail against the
pre-amendment fixture (anti-tautology check: reverted the fixture to its old
unconditional-purge form, confirmed this exact test fails with the same
purge-then-recompile signature measured above, then restored the fix).

## Second amendment: hardening for zero flake under real concurrent `-n4` load

A real full-suite `-n4` run (not the paired-session measurement above) surfaced
a genuine residual race the paired-session proof did not exercise: with the
purge removed, N real xdist workers now share ONE disk pickle via real
concurrent filesystem I/O -- something that never happened before this ADR
(the disk cache was previously off under pytest entirely, so there was no
disk-I/O race surface at all). Measured directly: the shared pickle's mtime
changed mid-suite even though no registry TOML content changed (confirmed via
`git log`; the pickle's content-derived filename/hash stayed identical too),
and 5 tests newly failed under `-n4` that pass cleanly in isolation. Root
cause: `os.replace` is atomic at the filesystem level, but a concurrent
reader's `open(cache_path, "rb")` can transiently observe an `OSError` while a
sibling worker's replace is in flight (a Windows-specific sharing-violation
window in particular); the existing broad `except Exception` swallowed this
and fell through to a full recompute+rewrite, which is safe (never serves
corrupt data) but defeats the sharing this ADR exists to deliver, and
additionally revealed that 2 of the new regression tests asserted EXCLUSIVE
state (file count, mtime) on the real shared `/tmp` pickle -- a false
assumption once sibling xdist workers are also touching it.

**Two fixes, both real-behavior, no mocks:**

1. **Read-retry on the disk-cache open.** `_read_registry_disk_cache_pickle`
   (new, `_loader.py`) retries the `open()` + `pickle.load()` up to 3 times
   with a short exponential backoff (10ms, 20ms) before giving up and falling
   through to recompute -- closing the transient replace-race window, which
   is sub-millisecond, with large margin. The broad `except Exception` is
   preserved as defence-in-depth for a genuinely corrupt/foreign file; it now
   logs at `.debug` on every attempt (satisfying this package's own
   broad-exception-must-log-or-raise hygiene gate,
   `test_registry_production_broad_exception_handlers_raise_or_log`).
2. **Test-owned cache-directory isolation.** `registry_disk_cache_dir()` (new,
   `_loader_cache.py`) reads an `AEAT_REGISTRY_DISK_CACHE_DIR` env-var override
   before falling back to `tempfile.gettempdir()`. The two tests that assert
   exclusive pickle state
   (`test_bundled_root_disk_cache_is_shared_across_processes`,
   `test_bundled_root_disk_cache_survives_across_separate_real_pytest_sessions`)
   now set this var to a `tmp_path`-owned directory (via `monkeypatch.setenv`
   for the parent process and an explicit `env=` entry for every spawned
   subprocess, since the var must reach both ends of a cross-process proof).
   Production and every other caller never set this var and keep using the
   real OS temp directory unchanged; only these two tests' own exclusive-state
   assertions are isolated from sibling xdist traffic -- the real filesystem,
   the real pickle read/write path, and the real bundled-root sharing
   mechanism are still exercised end-to-end, nothing is mocked.

The timing assertion in `test_bundled_root_disk_cache_is_shared_across_processes`
(a threshold on the child process's elapsed read time) was removed rather than
loosened: measured child-read times under this environment's variable
concurrent load (7.0s) overlapped the range a genuine cold compile itself
takes (6.7s-9s) on this codebase's registry size, so no fixed wall-clock
threshold can reliably distinguish "slow but correct cache-hit read" from "a
real recompile" here. The mtime/size identity check is the deterministic,
unambiguous proof (a rewrite touches both, unconditionally, on every real
filesystem) and remains the test's sole pass/fail signal.

**Verification:** three consecutive real `-n4` full-registry-suite runs (cold,
immediate warm repeat, and a third repeat under measurably heavier concurrent
load): the shared bundled pickle's mtime and size stayed byte-identical across
all three (zero rewrites), and the failure count returned to exactly the 6
pre-existing, unrelated prorrata-campaign failures on runs 1 and 2 (0 new).
Run 3, under heavier load, surfaced ONE additional failure
(`test_public_api_boundaries.py::test_source_tree_does_not_use_absolute_registry_private_imports`,
a source-tree AST scan) that passed cleanly in isolation. This was
**not** an instance of the general "loader-cache race" pattern this
codebase's own local-execution discipline documents; a later honesty
review traced it to a distinct, real defect in
`test_bundled_root_disk_cache_survives_across_separate_real_pytest_sessions`
itself, which materialised its throwaway scratch module directly inside
the real, AST-walked `src/aeat/domain/calculations/registry/tests/`
directory -- under heavier concurrent load its write/run/unlink window
raced a sibling worker's AST scan of that same directory (exactly the
directory `test_public_api_boundaries` also scans), surfacing as a
transient `FileNotFoundError`. That defect is fixed by relocating the
scratch module and its own minimal `conftest.py` (re-exporting the real
`_isolate_registry_caches` autouse fixture by absolute import) under the
test's own `tmp_path`, never under the tracked, walked tree.
