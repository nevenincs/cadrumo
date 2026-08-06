---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:2d4bfa8fe4b99a8475f303047267829cedc6e4c58a84b42864f80d1f1d2690a5'
step_id: 'S804'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# Hoist secure-storage runtime fixture from autouse function-scope to module scope across `application/filing/conftest.py`, `application/ledger/test_*.py`, `adapters/persistence/storage/sql/test_*.py`, `storage/envelope/test_*.py`, `storage/master_key/test_*.py`, `storage/secret_store/test_*.py`. Replace ~440 inline create_engine_from_settings + EphemeralMasterKeyProvider constructions with the module-scoped fixture. Use `Session().begin_nested()` for per-test isolation where roundtrip-anti-tautology tests demand it. Estimated savings 1.5-6 min sequential

## Scope

- `src/aeat/application/filing/conftest.py`

## Description

The step text specified a fixture-scope flip with `Session().begin_nested()` per-test isolation. The infeasibility audit established that `begin_nested` is never implemented anywhere and a savepoint cannot roll back the on-disk secure-storage artefacts (bucket directory, manifest, wrapped-DEK keystore, per-bucket SQLite) where the cross-test bleed lives. This step landed the redesign the audit called for: a real per-test on-disk reset, applied per surface.

- Reconcile the prior dead agent's uncommitted WIP on the filing conftest: finish and verify the module-scope hoist plus the autouse `_reset_filing_store` teardown that calls `reset_secure_object_store` (whole-table `secure_objects` DELETE) before each test. Add `__all__` to silence the fixture unused-function warning, matching the committed ledger conftest precedent.
- Remove the dead, false-docstring module-scope fixture from the four storage conftests (`sql`, `envelope`, `master_key`, `secret_store`). The fixture was not autouse and referenced by no test, so it never ran; every storage test already self-provisions a function-scoped `tmp_path` isolated runtime. Rewrite each docstring to describe the actual isolation model.
- The ledger surface (`_action_test_support.py` + conftest) was already landed by the peer commit that introduced `reset_secure_object_store`; no change owed there.

Modified: `src/aeat/application/filing/conftest.py`; `src/aeat/adapters/persistence/storage/{sql,envelope,master_key,secret_store}/conftest.py`.

## Outcome

S804 landed across the two surfaces that materially benefit. Filing: module-scope runtime provisioned once per module, per-test isolation restored by the reset teardown; 287 passed. Storage: dead aspirational fixtures removed, tests unchanged; 318 passed before and after (behaviour-preserving). Ledger: already landed. Gates ruff, ruff format, ty, pyright clean on every touched file.

Isolation bite-proof (isolation is load-bearing, not a false-green): with the filing reset disabled, `test_repository::test_list_returns_persisted_ids_sorted` and `test_complementaria_repository::test_list_and_iter` fail from persisted-id bleed (a prior test's rows appear in a later test's list assertion), reproducing audit finding S804-4 on the filing surface; with the reset restored they bite again and pass. The at-rest anti-tautology scan tests read the module runtime `storage_root`, not per-test `tmp_path`, so they remain compatible with the module-shared runtime.

The step text's "replace ~440 inline create_engine constructions" was not literally performed for the storage surfaces because those tests do not consume a shared fixture; the module-scope hoist there was dead and was removed rather than wired. S809 (`-n auto --dist=loadfile` default addopts) is a separate step, deferred pending an explicit go/no-go on its shared-worktree blast radius.

## Notes

Incident (peer no-pathspec commit sweep): the filing conftest was committed cleanly by explicit pathspec as its own commit. The four storage conftests were staged with an explicit `git add` pathspec, but before this agent's `git commit` ran, a peer agent's bare no-pathspec `git commit` swept the staged storage conftests into the peer commit `b3e726438e` (a `test_modelo_303_deductible_evidence_gate` typecheck fix) — the `subagent-commits-require-explicit-pathspec` failure mode. The storage-conftest content landed correctly and intact in HEAD; only its attribution is bundled under the peer SHA. No history rewrite was attempted (reset/rebase/revert are forbidden here); the content is correct and verified, so the mis-attribution is recorded as inventory rather than corrected destructively.
