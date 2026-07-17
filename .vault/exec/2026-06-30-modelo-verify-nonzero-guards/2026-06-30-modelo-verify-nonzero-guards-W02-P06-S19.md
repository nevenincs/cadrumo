---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S19'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Investigate the M714 total-cuota-integra-to-cuota-a-ingresar edge against the limite conjunto art. 31 cap, the Ceuta and Melilla bonificacion, and foreign-tax-credit deductions, decide whether a false-positive-free ADVISORY condition exists, and either author it with grounded legal_refs plus a two-tier test pair or record the wontfix rationale as a vault audit finding

## Scope

- `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/verification_expectations/0001-verification_predicates.toml`

## Description

- Re-confirm `patrimonio.total-cuota-integra` (40), `patrimonio.cuota-minorada` (45), and `patrimonio.cuota-a-ingresar` (55) are all `input_kind = "manual"` with no formula linkage, against `casillas/0001-casillas.toml`.
- Read the bundled corpus for Ley 19/1991 art. 31 (limite conjunto) and confirm the registry already computes the art. 31 80% floor reference (`patrimonio.reduccion-limite-80`, casilla 39) -- so the limite-conjunto mechanism alone leaves a 20% floor, not a path to zero.
- Search the legal catalogue (`legal/patrimonio.toml`) and the bundled corpus (`corpus/normatives/html/ley-19-1991-*`) for Ley 19/1991 art. 32 (deduccion impuestos extranjero) and art. 33 (bonificacion Ceuta/Melilla); confirm neither article is grounded anywhere in this codebase.
- Confirm the M714 casilla set has no casilla recording either deduction having been applied, so no registry signal exists to exclude a legitimate full offset from a silent omission.
- Decide: no false-positive-free ADVISORY condition is expressible for this edge today; record the wontfix rationale as a vault audit finding rather than authoring a guard.
- Persist the rationale and the prerequisite (ground arts. 32/33, add their casillas, wire them into the chain) in `.vault/audit/2026-06-30-modelo-verify-nonzero-guards-audit.md`.
- Confirm `test_modelo_714_riskier_edges_remain_unguarded` (updated under `W02.P06.S18`) also locks this edge's predicate id absence and cites the audit document.

## Outcome

Decision: **documented non-guard (wontfix-for-now)**. The `total-cuota-integra -> cuota-a-ingresar` edge is not guardable today: the limite conjunto (Ley 19/1991 art. 31) is already confirmed bounded by the registry's own `patrimonio.reduccion-limite-80` 20%-floor reference, so it alone cannot legitimately zero `cuota-a-ingresar` -- but Ley 19/1991 art. 32 (deduccion por impuestos satisfechos en el extranjero) and art. 33 (bonificacion Ceuta/Melilla, 75%) are confirmed-real legitimate full/near-full offset mechanisms that are entirely unmodelled in this codebase: no legal-catalogue entry, no bundled corpus file, no casilla. A predicate over the existing casilla set cannot distinguish a taxpayer who legitimately applied either deduction from an operator who simply omitted casilla 55. The rationale, the legal grounding, and the concrete prerequisite (ground arts. 32/33 against bundled BOE corpus, add their casillas, wire them into the cuota-minorada/cuota-a-ingresar chain) are persisted in the `modelo-verify-nonzero-guards` audit document. No new predicate was authored.

## Notes

No incidents. This Step shares its registry investigation and audit document with `W02.P06.S18` (both M714 edges are documented in one audit, per the Phase's shared scope); the `test_modelo_714_riskier_edges_remain_unguarded` regression strengthened under `S18` covers both predicate-id absences and is not duplicated here. No engine, schema, or operator change was made. Full focused test run (`test_modelo_714_registry.py`, `test_verification_m714_advisory.py`): 25 passed.
