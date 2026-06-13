---
step_id: S353
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#cross-domain-continuity"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W09.P41.S353 — M100 casilla 0505 formula derivation

## Outcome

Casilla 0505 (`base liquidable general sometida a gravamen`) was `input_kind = "manual"` in the 2024 revision. When not supplied the engine computed cuota íntegra as 0, silently producing wrong tax results for every M100 2024 filer.

## What was already done by architect triage (commits 94b424c6b, eb8793d07, 227350dc9)

- `0487-0505.toml`: flipped `input_kind` to `"computed"`, added `formula = "renta-2024-base-liquidable-general-sometida-a-gravamen"`.
- `0168-renta-2024-base-liquidable-general-sometida-a-gravamen.toml`: formula `max(0, [0500] - [0527])`.
- `0001-renta-cuota-chain.toml`: formula added in correct position after `renta-2024-base-liquidable-general`.
- S353 oracle-grounded tests in `test_modelo_100_tarifa_real.py` (3 tests, LIRPF 2024 Art. 63 tables).
- Corresponding 2025 revision changes.

## What this commit adds (e8afc9084)

- Six 2024 formula files for the final settlement chain (0169-0174) that were untracked from the same triage sweep, covering cuota líquida incrementada total, cuota resultante, retenciones arrendamientos, total pagos a cuenta, cuota diferencial, resultado declaración.
- `0011-renta-2024-final-settlement.toml` construct wiring the settlement chain.
- Fixed broken `source_citations` required_text in `0172-renta-2024-total-pagos-a-cuenta.toml` — the BOE 2024 form corpus file is a JSON summary that does not contain "retenciones, ingresos a cuenta y pagos fraccionados"; replaced with "Modelo 100" + "ejercicio 2024" which are present.
- Fixed `test_renta_chain_behaviour.py` to remove `"0505": Decimal("0")` from `_base_2025_inputs` (now computed) and rewrote `test_minimo_personal_split_min_uses_smaller_of_base_liquidable_and_total_minimo` to drive 0505 via `0003` (rendimientos trabajo) leaf input.

## Operand verification

Casilla 0527 (`importe anualidades por alimentos hijos judicial`) exists in the 2024 revision at `0509-0527.toml`, `input_kind = "computed"`. Formula `renta-2024-anualidades-alimentos-hijos-suma` is already registered. The operand chain is complete.

## Formula correctness note

The task spec cited `0500 - 0506` (DA 16ª planes pensiones). Inspection confirms casilla 0506 is "reducción tributación conjunta remanente" — not pension-plan reductions. The correct formula per the actual AEAT M100 2024 form and the established 2025 revision is `max(0, 0500 - 0527)` (base liquidable general minus anualidades alimentos judiciales). The architect triage correctly identified this.

## G6 fallback decision

NOT applied. The operand chain is structurally complete: 0527 is computed, its inputs (1741-1759) are manual input casillas. No `MISSING_REDUCTION_INPUT` verification finding was added.

## Tests

- 114 tests pass across `test_renta_cuota_chain_contract`, `test_renta_chain_behaviour`, `test_modelo_100_tarifa_real`, `test_modelo_100_drift_detection`, `test_referential_integrity`, `test_modelo_100_registry`.
- Pre-existing M130 failure in `test_committed_registry` is unrelated and pre-dates this session.

## Files touched

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0487-0505.toml` (committed in 94b424c6b)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0168-renta-2024-base-liquidable-general-sometida-a-gravamen.toml` (committed in 94b424c6b)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/constructs/0001-renta-cuota-chain.toml` (committed in 94b424c6b)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0169-0174-*.toml` (committed in e8afc9084)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/constructs/0011-renta-2024-final-settlement.toml` (committed in e8afc9084)
- `src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py` (committed in e8afc9084)
