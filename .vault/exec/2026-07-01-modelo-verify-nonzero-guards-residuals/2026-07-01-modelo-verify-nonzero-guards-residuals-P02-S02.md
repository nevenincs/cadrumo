---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards-residuals'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S02'
related:
  - "[[2026-07-01-modelo-verify-nonzero-guards-residuals-plan]]"
---

# Add canary tests pinning the three documented non-guards, each citing the residuals research by name

## Scope

- `src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py`
- `src/aeat/domain/calculations/registry/tests/test_modelo_714_registry.py`

## Description

- Rewrite the M202 clave-33 canary (`test_committed_modelo_202_minimo_a_ingresar_cn_10m_remains_unguarded`) to cite `2026-07-01-modelo-verify-nonzero-guards-residuals-research` by name, reflect that DA-14a is now grounded (Finding 1b), state the real deferral cause (Finding 1d: INCN profile-fact/numeric-threshold signals structurally unreachable), and add a real-behaviour assertion that `ley-27-2014:da-14` is now in clave 33 legal_refs while the predicate stays absent.
- Split the combined M714 non-guard canary into two per-edge canaries: `test_modelo_714_base_liquidable_edge_remains_unguarded` (Finding 2, art. 28 minimo exento) and `test_modelo_714_cuota_a_ingresar_edge_remains_unguarded` (Finding 3, art. 31/32/33 + CCAA bonificacion up to 100% in Madrid/Andalucia), each citing the residuals research by name and asserting both the predicate absence and that the edge casillas are manual with no formula linkage.

## Outcome

- The three documented non-guards are each pinned by a canary citing the residuals research by name, so a future prerequisite landing (profile-fact value channel, numeric-threshold operator, CCAA minimo-exento/bonificacion tables) is forced to revisit the decision.
- Both test files pass `python -m py_compile` and `ruff check`; the M202 file is `ruff format --check` clean.

## Notes

- Running the canaries via pytest is currently blocked by the same unrelated peer convenio relocation that reds the registry package import (`ConvenioRateRow` -> `ConvenioAuthority`, `_registry_schema_support.py` not yet swept). Verification was therefore py_compile + ruff + direct inspection of the registry TOMLs proving the asserted casillas are manual/unlinked and the predicate ids are absent; the canaries will execute green once the peer relocation completes. Owner-attributed to the peer, not this feature (`full-tree-gate-must-distinguish-owner`).
- `test_modelo_714_registry.py` carried a peer cosmetic autoformat hunk (a collapsed multi-line assert near line 191) at edit time. My edits are in a disjoint region (the non-guard canaries); the commit staged a HEAD-anchored blob carrying only my hunks via the apply-cached / cacheinfo gated drive, preserving the peer WIP in the working tree.
