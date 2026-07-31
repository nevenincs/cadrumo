---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:64cd28e87bd70ba7d8c2c681cfd9961bc0a32f0ab2d0572310be52aa7e88941f'
step_id: 'S13'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Add a registry-shape test asserting predicate_id, expression, finding_kind, and legal_refs for the new M714 cuota-integra-to-total-cuota-integra advisory on the loaded 2021-y-siguientes revision snapshot

## Scope

- `src/aeat/domain/calculations/registry/tests/test_modelo_714_registry.py`

## Description

- Add `test_modelo_714_carries_cuota_integra_under_declaration_advisory`, asserting the loaded 2021-y-siguientes snapshot carries the `modelo-714-cuota-integra-implica-total-cuota-integra` predicate with the expected expression, `ADVISORY` finding_kind, and `ley-19-1991:art-30` legal ref.
- Add `test_modelo_714_riskier_edges_remain_unguarded`, asserting the two deliberately-deferred M714 edges (base-imponible to base-liquidable; total-cuota-integra to cuota-a-ingresar) are absent from the predicate set, keeping the deferral scope honest and self-checking for the Wave W02 follow-up.
- Both tests load the predicate set off `build_snapshot`, mirroring the existing M200 `test_modelo_200_carries_manual_handoff_under_declaration_advisory_predicates` registry-shape pattern.

## Outcome

`uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_modelo_714_registry.py -q` passes 21/21 (19 pre-existing parametrized/unit tests plus the 2 new ones), confirming no regression to the existing M714 cuota-integra-escala and art-31-manual-tail coverage.

## Notes

None.
