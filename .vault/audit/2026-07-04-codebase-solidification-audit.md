---
tags:
  - '#audit'
  - '#codebase-solidification'
date: '2026-07-04'
modified: '2026-07-04'
body_hash: 'sha256:c768d457407c9d89624dbc8732972d35e092e8472fb695bf703cc5d5b810e81d'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification audit: W30.P64.S804 module-scope infeasibility and S809 precondition

## Scope

Investigation of plan steps `W30.P64.S804` (hoist the secure-storage runtime
fixture from function-scope autouse to module scope across the filing, ledger,
and storage test surfaces) and `W30.P64.S809` (`-n auto --dist=loadfile` as the
default pytest addopts), which the user authorised for landing after they were
initially deferred. Both were investigated with empirical isolation probes.

## Finding S804-1: the begin_nested isolation mechanism does not exist

The plan and four storage conftests describe per-test isolation via
`Session().begin_nested()` transactional rollback. A repository-wide search finds
`begin_nested` only inside docstrings; it is never called in any fixture or test.
The rollback teardown the module-scope hoist depends on was specified but never
implemented for any surface. The docstrings assert an isolation guarantee the
code does not provide.

## Finding S804-2: begin_nested cannot isolate the bleed source even if built

The secure-storage runtime provisions real on-disk artefacts: a bucket
directory, plaintext manifest, a separated wrapped-DEK keystore, and a per-bucket
SQLite database under a storage root. The `SecureObjectRepository` and the
profile transaction catalogue commit to that persistent store, not to an open
transaction a savepoint could roll back. A per-test savepoint would isolate DB
rows only, never the keystore mints, manifest, attachment bytes, or the persisted
transaction catalogue that the cross-test bleed originates from. Tests that assert
against per-test `tmp_path` filesystem state additionally break under a
module-shared `tmp_path_factory` storage root.

## Finding S804-3: filing hoist was already attempted and reverted

Commit `9fac9c2284` reverted `_active_bucket_runtime` in
`application/filing/conftest.py` from module-scope back to function-scope autouse,
with a post-mortem documenting the exact failure: module-shared storage root broke
per-test `tmp_path` payload-path lookups, and persisted-ID bleed let one test's
records appear in another's list/iter assertions. The filing conftest docstring
records this as intentional. Filing is green at HEAD on function-scope: 276
passed in 158 s.

## Finding S804-4: ledger module-scope destroys isolation (empirical)

Module-scoping the shared ledger `secure_objects` fixture
(`application/ledger/tests/_action_test_support.py`) from function-scope to
`scope="module"` with `tmp_path_factory` and running the bleed-sensitive and
anti-tautology modules produced 13 failures from persisted-ID bleed: the
transaction catalogue accumulated rows across tests in the module
(`entries=13`, `entries=14` in the persistence log), and idempotency and
anti-tautology assertions
(`test_zero_amount_add_is_refused_not_silently_deduped`,
`test_same_key_differing_only_in_recargo_raises_conflict`,
`test_keyed_add_three_retries_still_one_row_one_event`) stopped biting. The
experimental edit was restored to HEAD; the previously-failing idempotency module
returns to 13 passed. This reproduces the filing revert's failure mode on the
ledger surface.

## Finding S804-5: storage surfaces already module-scoped and green

`adapters/persistence/storage/{sql,envelope,master_key,secret_store}` already
carry module-scoped (non-autouse) `_active_bucket_runtime` fixtures at HEAD from
prior work, and pass: 318 passed. No change is owed there. These surfaces avoid
bleed because their tests do not persist-and-list shared mutable catalogue state
in the way the filing and ledger repository tests do; they are not evidence that
the filing or ledger surfaces can be safely hoisted.

## Decision S804: not landed

No safely-landable new S804 batch exists. Hoisting the filing or ledger surfaces
re-introduces persisted-ID bleed and breaks anti-tautology isolation, which the
roundtrip discipline forbids. A correct hoist would require building a real
per-test teardown that also resets the on-disk secure-object store and keystore
between tests (not the fictional begin_nested), which is a substantive redesign
beyond a fixture-scope change. The step is left unchecked. The four storage
surfaces are already module-scoped.

## Finding S809: functionally safe on slice, but precondition unmet

A `-n auto --dist=loadfile` slice over the storage surfaces plus registry
authority and manual-worked-example tests passed: 331 passed in 20.5 s, with no
registry-compile blowup (the per-worker `lru_cache` compiled once per worker) and
no parallel-induced failures. The change is functionally safe on this slice.
However, S809's stated precondition ("S804 has landed so module-scoped fixtures
actually reduce work across workers") is unmet because S804 did not land, and
S809 flips the default test execution for every concurrent agent in this shared
worktree. Given the failed precondition, the high blast radius, and the
documented loader-cache race hazard under parallel pytest that a single slice
cannot rule out for the full suite, the default-addopts change was not committed
unilaterally; it is reported for a coordinator/user decision on whether to
proceed independently of S804.

## Recommendation

Treat S804 as blocked on a per-test secure-storage teardown redesign, not a
fixture-scope flip. Consider correcting the four storage conftest docstrings that
claim begin_nested isolation the code does not implement. Decide S809 explicitly
given that its S804 precondition cannot be satisfied.
