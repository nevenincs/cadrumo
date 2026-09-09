---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:aed074e2a0a6b3f5d7f095f21db8d8961925b09024f55f86b8bce8eb6450249f'
step_id: 'S258'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unreachable filing export replay custody adapter and its self-contained synthetic tests because no product or development composition supplies it to the proof executor; remove any now-ownerless secure-object namespace registration, correct stale reachability reference prose, run focused secure-storage and proof gates, remeasure exact reachability, update the cadence reference, and write the Step Record.

## Scope

- `filing export replay custody adapter and tests`
- `secure object namespace authority`
- `stale reachability reference`
- `focused gates`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `D` `src/cadrumo/adapters/persistence/profile/filing_export_replay.py`
- `D` `src/cadrumo/adapters/persistence/profile/tests/test_filing_export_replay_custody.py`
- `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `M` `.vault/reference/2026-09-02-unreachable-capability-disconnected-capability-inventory-reference.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py dev/registry/tests/test_filing_export_two_channel_proof.py dev/registry/tests/test_filing_export_live_proof.py dev/registry/tests/test_pinned_conformance_vector.py src/cadrumo/application/filing/tests/test_export_proof_contracts.py` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The relevant focused lane passed 41 tests; the namespace discovery test remains red on five unrelated namespaces absent from the peer-modified registry (`cadrumo.workflow`, `cadrumo.domain.attachments.blobs`, `cadrumo.google.oauth.client`, `cadrumo.outbound.aeat.auth.sessions`, and `cadrumo.domain.transactions.bucket`). This Step did not absorb or suppress that drift. Exact reachability improved from 32 to 31 unreachable modules with symbols unchanged at 287.
