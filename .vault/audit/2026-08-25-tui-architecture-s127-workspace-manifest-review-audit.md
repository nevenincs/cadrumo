---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e13190fb36db1688bf4e7830dc7b2fb55c61ae7459b75b9fb84194d0153f62d7'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `S127 workspace manifest review`

## Scope

Independent final-state review of S127 after commits `db8c0e0909`, `3797210a1a`, and `792cc30f68`, using the accepted Workspace V1 D8 contract, the S127 research reference, current S127 Step Record, Vaultspec RAG discovery on port 8766, and exact source census. Audited the public `RegistrySnapshot` and `selector_model_for_source` roots, recursive Pydantic traversal, deterministic manifest digest/fixed point, classification metadata, generated export delegation, S125/S126 reuse, facade topology, and focused static/test gates.

## Findings

### focused-ruff-gate | medium | The final S127 test module fails the required Ruff gate

`uv run --no-sync ruff check src/cadrumo/application/modelo/_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py` reports I001: the new `_Node` import is out of RuffÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢s required ordering in `test_workspace_manifest.py`. The current tree therefore does not satisfy the requested focused quality gate. This is a mechanical correction in the test only, but it must be repaired and the focused gate rerun before S127 can be approved.

### focused-ruff-gate-resolution | low | The S127 focused quality gate is restored

Commits `9cd9ee92231`, `047146dc00`, and `de9f4d073f` resolve the recorded mechanical formatting issue while preserving the production authority fixture. The final test obtains its snapshot exclusively through `resources().modelos.authority.snapshot(...)`; it carries no isolated snapshot builder or xfail. Re-review confirms focused Ruff lint and format checks pass, basedpyright reports zero findings, and the reported focused integration suite passes 5 tests. The final manifest and facade retain the reviewed public-facade-only topology.
## Recommendations

- Resolve `focused-ruff-gate` by applying the formatterÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢s import order, then rerun the focused integration, Ruff, and basedpyright gates against a quiescent S127 tree.

## Disposition

PASS. The recorded MEDIUM quality-gate finding is resolved by the final mechanical commits and repeatable focused verification. No HIGH or CRITICAL architecture defect was found in the inspected final shape: the manifest traverses `RegistrySnapshot.model_fields` rather than a count or denominator allowlist; `_REGISTRY_ROOT_FIELDS` is a fail-closed classification guard, so a new top-level snapshot field is traversed and then raises until deliberately classified. The current facade is eager and carries no lazy `__getattr__`, lazy bridge, removed lazy-facade test, or manifest re-export. RAG returned the sole live authority without an index-lag warning; exact census found no parallel manifest authority or private-registry import. The 1,731-entry real M303 authority result is intentionally not hardcoded as a pass count, consistent with D8ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢s no-count denominator rule; its sorted/digested fixed point is the operative proof.
