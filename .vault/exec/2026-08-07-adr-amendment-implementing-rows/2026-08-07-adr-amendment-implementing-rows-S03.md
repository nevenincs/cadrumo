---
tags:
  - '#exec'
  - '#adr-amendment-implementing-rows'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:a636af96c687859c14da2cc65b6b4ba94a66f23a23f94333b9b642b8d7f61ff2'
step_id: 'S03'
related:
  - "[[2026-08-07-adr-amendment-implementing-rows-plan]]"
---

# Test each of the four unmodelled M390 regimen blocks for a rate-blind total before applying the two-layer rate-box shape, per the rate-box-evidence-assertion-adr amendment's precondition

## Scope

- `src/cadrumo/registry/aeat/modelos/390/`

## Description

- Read the accepted rate-box decision, its source research, and the authoritative Modelo 390 revision through the registry authority.
- Derive the four candidate blocks from the research and their 2024 rate-box rows from the bundled AEAT record design.
- Add a real-authority gate that requires a block-specific rate-blind total before its official rate boxes may enter a two-layer partition.
- Prove the admission guard detects a candidate official box introduced into a live partition through an in-memory strict-registry mutation.

## Outcome

Intragrupo, criterio de caja, bienes usados, and agencias de viajes each have
official rate boxes but no block-specific rate-blind total in the 2024 design.
Box [34] totals multiple devengada blocks and cannot act as a sibling total for
any individual candidate. The two-layer shape is therefore not applied to any
of the four; the new gate keeps that conclusion load-bearing until evidence for
a block-specific total exists.

## Verification

```
uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_modelo_390_unmodelled_regimen_rate_box_preconditions.py src/cadrumo/domain/calculations/registry/tests/test_modelo_390_rate_box_total_invariant.py src/cadrumo/domain/calculations/registry/tests/test_modelo_390_rate_box_layer.py src/cadrumo/domain/calculations/registry/tests/test_modelo_390_recargo_rate_box_layer.py src/cadrumo/domain/calculations/registry/tests/test_modelo_390_rate_box_export_offsets.py src/cadrumo/domain/calculations/registry/tests/test_modelo_390_rate_box_reachability.py
70 passed in 26.88s

uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/tests/test_modelo_390_unmodelled_regimen_rate_box_preconditions.py
All checks passed!

uv run --no-sync basedpyright src/cadrumo/domain/calculations/registry/tests/test_modelo_390_unmodelled_regimen_rate_box_preconditions.py
0 errors, 0 warnings, 0 notes

uv run --no-sync vaultspec-core vault check all --fix --feature adr-amendment-implementing-rows
Vault Check  - All
Total: 3 fixed
```

## Notes

No Modelo 390 registry authoring changed: the precondition is absent for every
candidate, so adding a rate-box partition would contradict the accepted ADR.
