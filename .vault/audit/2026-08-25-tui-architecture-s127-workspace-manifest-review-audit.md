---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d66f18ef4494e201b302d728cc0d6e5b54fb9846547278b3501777243e82a730'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `S127 workspace manifest review`

## Scope

Independent final-state review of S127 after commits `db8c0e0909`, `3797210a1a`, and `792cc30f68`, using the accepted Workspace V1 D8 contract, the S127 research reference, current S127 Step Record, Vaultspec RAG discovery on port 8766, and exact source census. Audited the public `RegistrySnapshot` and `selector_model_for_source` roots, recursive Pydantic traversal, deterministic manifest digest/fixed point, classification metadata, generated export delegation, S125/S126 reuse, facade topology, and focused static/test gates.

## Findings

### focused-ruff-gate | medium | The final S127 test module fails the required Ruff gate

`uv run --no-sync ruff check src/cadrumo/application/modelo/_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py` reports I001: the new `_Node` import is out of Ruffâ€™s required ordering in `test_workspace_manifest.py`. The current tree therefore does not satisfy the requested focused quality gate. This is a mechanical correction in the test only, but it must be repaired and the focused gate rerun before S127 can be approved.

## Recommendations

- Resolve `focused-ruff-gate` by applying the formatterâ€™s import order, then rerun the focused integration, Ruff, and basedpyright gates against a quiescent S127 tree.

## Disposition

FAIL pending the MEDIUM quality-gate repair and repeatable focused-test run. No HIGH or CRITICAL architecture defect was found in the inspected final shape: the manifest traverses `RegistrySnapshot.model_fields` rather than a count or denominator allowlist; `_REGISTRY_ROOT_FIELDS` is a fail-closed classification guard, so a new top-level snapshot field is traversed and then raises until deliberately classified. The current facade is eager and carries no lazy `__getattr__`, lazy bridge, removed lazy-facade test, or manifest re-export. RAG returned the sole live authority without an index-lag warning; exact census found no parallel manifest authority or private-registry import. The 1,731-entry real M303 authority result is intentionally not hardcoded as a pass count, consistent with D8â€™s no-count denominator rule; its sorted/digested fixed point is the operative proof.
