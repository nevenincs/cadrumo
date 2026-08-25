---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:fb1304eed44cea5c12d484caa6c6c22d7f659b8535a584bff0fe1355c4c508f7'
step_id: 'S126'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define ModeloWorkspaceProducerContractV1, stamped contributing projections, owner-scoped ABA-safe epochs, atomic projection-plus-epoch ports, and the generated producer-contract inventory that rejects missing, duplicate, or stale contributors

## Scope

- `src/cadrumo/application/modelo/_workspace_producers.py`
- `src/cadrumo/application/modelo/tests/test_workspace_producers.py`

## Description

- Define the sole strict Workspace producer contract, projection-schema fingerprint, exact producer stamp, owner-generation epoch, and generic atomic capture record.
- Declare the typed atomic producer port with capture and second-pass current-coordinate reads, without implementing any canonical owner or Workspace assembly.
- Generate the eight-category producer inventory with reproducible digests and refusal of missing, duplicate, unclassified, stale, or reordered contracts.
- Add integration adversaries for stamp, owner, schema, ABA, inventory fixed-point, missing, duplicate, unclassified, and stale-contract drift.

## Outcome

The S126 producer boundary is review-ready. It reuses S125 contributor identities and introduces no registry grammar, producer implementation, assembly/retry authority, callback, shim, alias, fallback, or re-export bridge. S126 remains open pending independent review; this record does not close the plan step.

## Verification

- Vaultspec RAG located the accepted Workspace contracts; its current code index had no matching producer implementation. Exact `rg` census found no existing `ModeloWorkspaceProducerContract`, producer stamp, epoch, contributing projection, atomic port, or producer inventory definition under `src`.
- `uv run --no-sync ruff check src/cadrumo/application/modelo/_workspace_producers.py src/cadrumo/application/modelo/tests/test_workspace_producers.py` passed.
- `uv run --no-sync basedpyright src/cadrumo/application/modelo/_workspace_producers.py src/cadrumo/application/modelo/tests/test_workspace_producers.py` reported 0 errors, 0 warnings, 0 notes.
- `uv run --no-sync pytest -q -o addopts='' -m integration src/cadrumo/application/modelo/tests/test_workspace_producers.py` passed with 6 tests.

## Notes

No plan structure or completion status was changed.
