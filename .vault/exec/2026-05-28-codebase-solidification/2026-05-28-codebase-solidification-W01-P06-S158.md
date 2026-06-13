---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S158'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W01.P06.S158`

Add two real-behavior tests to `test_observations_repository.py` exercising the `IvaWalletDecisionRepository.load_decision` bridge: one for the primary hashed-key path and one for the legacy cleartext-key fallback path.

- Modified: `src/aeat/application/calculations/test_observations_repository.py`

## Description

`test_load_decision_returns_hashed_key_record`: saves a decision via `repo.save_decision` (keyed under the sha256 digest), loads it via `load_decision`, asserts equality. Confirms the primary path works with a real isolated encrypted SQLite store.

`test_load_decision_falls_back_to_legacy_cleartext_key`: writes an envelope directly to `repo._objects.save` under the legacy cleartext key (`{nif}:{year}:{period}`) to simulate a pre-hardening persisted record. Calls `load_decision` and asserts the result equals the original decision. Confirms the fallback branch in `load_decision` is reachable and functional. If the bridge is prematurely removed, this test fails loudly.

Both tests use `isolated_runtime_profile` (real ephemeral encrypted SQLite, real master key provider) — no mocks.

## Tests

Both new tests passed in the targeted run (23/23 passed, 47 s). Commit SHA: 74f07401b.
