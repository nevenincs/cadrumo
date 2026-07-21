---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-08'
step_id: 'S398'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-task-226 M131 cuota-minima regulatory floor authoring gated on Orden EHA/672/2007 modulo-tariff corpus landing under task 226

## Scope

- `structural implies_nonzero(C01 C07) attempt rolled back at c159966df because the formula DAG does not connect C01 to C07 via the page-1 chain (C07 = C02+C04+C06 only)`
- `this Step now tracks the regulatory-floor predicate authoring waiting for the corpus blocker`
- `src/aeat/_data/registry/aeat/modelos/131/`

## Description

- Re-ground the S398 row with `vaultspec-rag` against the current M131 registry, the prior rollback record, and the shipped verification predicate implementation.
- Confirm the existing M131 regulatory-floor predicate is the DAG-correct lane: `implies_nonzero(["01", "02"])` as an `ADVISORY`, not the rolled-back `implies_nonzero(["01", "07"])` shape.
- Add committed-registry regression coverage for all shipped M131 revisions proving the predicate expression, finding kind, legal refs, formula-DAG relationship for C07, revision source refs, verification expectation source refs, and bundled corpus evidence.
- Review the change with a read-only code-review agent and rerun focused M131 registry and application verification gates.

## Outcome

The S398 regulatory-floor authoring blocker is closed without changing M131 registry data. The current registry already carries the honest predicate shape across `2019-2023`, `2024`, `2025`, and `2026`: positive C01 datos-base rendimientos require C02 pago fraccionado to be non-zero as an advisory. The old C01-to-C07 assertion remains absent, and the regression test proves why: C07 is the sum of C02, C04, and C06, so C01 is not a direct C07 input in the formula DAG.

Grounding is now explicit in tests. The M131 revision and verification expectation carry `aeat-modelo-131-instructions`; the predicate cites `rd-439-2007:art-110`; the revision carries `orden-eha-672-2007:art-3`; and the test reads the bundled corpus text for RD 439/2007 art. 110, Orden EHA/672/2007 art. 3, and the AEAT M131 instructions.

Validation:

- `uvx vaultspec-rag search "Modelo 131 cuota minima Orden EHA 672 2007 modulo tarifa corpus C01 C07" --type code`
- `uvx vaultspec-rag search "W04.P19.S398 Modelo 131 regulatory floor predicate" --type vault --doc-type plan`
- `uvx vaultspec-rag search "Modelo 131 regulatory floor predicate implies_nonzero 01 02 C07 formula" --type code`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_modelo_131_registry.py src/aeat/domain/calculations/registry/tests/test_modelo_131_regulatory_floor_predicate.py src/aeat/application/modelo/tests/test_verification_m131_advisory.py -q -p no:cacheprovider` passed with 35 tests.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/tests/test_modelo_131_regulatory_floor_predicate.py` passed.

## Notes

Predicate objects do not carry `source_refs`, so the test intentionally proves source grounding through the committed revision, verification expectation, source catalogue, and corpus files instead of overclaiming predicate-local source refs.

The code-review agent reported no findings. Residual risk remains outside this Step: M131 C01/C02 are still manual/advisory lanes until a future módulos-table calculation oracle models the annual Orden de módulos determination. This Step only closes the regulatory-floor predicate authoring and evidence guard.

A transient authority-load failure surfaced during one broad application test run while unrelated M100 2025 registry files were being edited concurrently. A rerun after the concurrent WIP settled passed the authority-dependent M131 advisory tests; no S398 code changes were required for that blockage.
