---
tags:
  - '#plan'
  - '#renta-cuota-integra-state-scale'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-renta-cuota-integra-state-scale-adr]]"
  - "[[2026-05-08-renta-cuota-integra-state-scale-research]]"
---
# `renta-cuota-integra-state-scale` plan

Implementation plan grounded in the
`renta-cuota-integra-state-scale-adr` decision: wire the IRPF state
progressive bracket parameters into Modelo 100's cuota chain via two
`lookup_bracket` formulas per ejercicio (one for casilla 0528 against
casilla 0505 base liquidable general, one for casilla 0530 against
casilla 0521 mínimo personal y familiar). Six ejercicios in scope:
2020, 2021, 2022, 2023, 2024, 2025.

## Proposed Changes

Per ejercicio Y in {2020, 2021, 2022, 2023, 2024, 2025}:

1. Add `[[revisions."{Y}".formulas]]` declaration with
   `id = "renta-{Y}-cuota-escala-estatal-sobre-base-liquidable-general"`,
   `target = "0528"`,
   `expression = { op = "lookup_bracket", args = [{ casilla = "0505" }, { parameter = "renta-{Y}-escala-estatal-base-general" }] }`,
   `rounding = "money-2"`,
   `legal_refs = ["ley-35-2006:art-62", "ley-35-2006:art-63"]`,
   `source_refs = ["lirpf-cuota-chain-authority"]`,
   plus a `[[...formulas.source_citations]]` block with required text
   `["escala general", "base liquidable general"]`.
2. Add a sibling formula targeting `0530` against `0521`, with id
   `renta-{Y}-cuota-escala-estatal-sobre-minimo-personal-familiar`
   and `legal_refs = ["ley-35-2006:art-62", "ley-35-2006:art-63", "ley-35-2006:art-67"]`.
3. Remove `f"renta-{Y}-escala-estatal-base-general"` from
   `_PRE_STAGED_PARAMETERS` in
   `src/aeat/domain/calculations/registry/test_modelo_100_drift_detection.py`.
4. Run `pytest src/aeat/domain/calculations/registry/test_modelo_100_drift_detection.py`
   and confirm all 8 drift-detection tests still pass for that year.
5. Run the workbook-parity test to verify the bracket arithmetic
   matches AEAT's authoritative output for the year.
6. Commit and push the year's work as a single, focused commit so
   merge-collision risk against concurrent registry work is
   minimised.

## Tasks

- Phase 1 — Foundation (ejercicio 2020)
  1. Step 1.1 — Add 0528 lookup_bracket formula to revision 2020
  1. Step 1.2 — Add 0530 lookup_bracket formula to revision 2020
  1. Step 1.3 — Drop renta-2020-escala-estatal-base-general from `_PRE_STAGED_PARAMETERS`
  1. Step 1.4 — Run drift-detection + workbook parity for 2020
  1. Step 1.5 — Commit + push 2020 wiring

- Phase 2 — Backport to 2021
  1. Step 2.1 — Add 0528 lookup_bracket formula to revision 2021
  1. Step 2.2 — Add 0530 lookup_bracket formula to revision 2021
  1. Step 2.3 — Drop renta-2021-escala-estatal-base-general from `_PRE_STAGED_PARAMETERS`
  1. Step 2.4 — Run drift-detection + workbook parity for 2021
  1. Step 2.5 — Commit + push 2021 wiring

- Phase 3 — Backport to 2022
  1. Step 3.1 — Add 0528 lookup_bracket formula to revision 2022
  1. Step 3.2 — Add 0530 lookup_bracket formula to revision 2022
  1. Step 3.3 — Drop renta-2022-escala-estatal-base-general from `_PRE_STAGED_PARAMETERS`
  1. Step 3.4 — Run drift-detection + workbook parity for 2022
  1. Step 3.5 — Commit + push 2022 wiring

- Phase 4 — Backport to 2023
  1. Step 4.1 — Add 0528 lookup_bracket formula to revision 2023
  1. Step 4.2 — Add 0530 lookup_bracket formula to revision 2023
  1. Step 4.3 — Drop renta-2023-escala-estatal-base-general from `_PRE_STAGED_PARAMETERS`
  1. Step 4.4 — Run drift-detection + workbook parity for 2023
  1. Step 4.5 — Commit + push 2023 wiring

- Phase 5 — Backport to 2024
  1. Step 5.1 — Add 0528 lookup_bracket formula to revision 2024
  1. Step 5.2 — Add 0530 lookup_bracket formula to revision 2024
  1. Step 5.3 — Drop renta-2024-escala-estatal-base-general from `_PRE_STAGED_PARAMETERS`
  1. Step 5.4 — Run drift-detection + workbook parity for 2024
  1. Step 5.5 — Commit + push 2024 wiring

- Phase 6 — Forward to 2025
  1. Step 6.1 — Add 0528 lookup_bracket formula to revision 2025
  1. Step 6.2 — Add 0530 lookup_bracket formula to revision 2025
  1. Step 6.3 — Drop renta-2025-escala-estatal-base-general from `_PRE_STAGED_PARAMETERS`
  1. Step 6.4 — Run drift-detection + workbook parity for 2025
  1. Step 6.5 — Commit + push 2025 wiring

- Phase 7 — Closure verification
  1. Step 7.1 — Confirm `_PRE_STAGED_PARAMETERS` is empty (or
     contains only autonomic-scale entries documented as
     out-of-scope here).
  1. Step 7.2 — Run the full drift-detection + parity-test suite
     against the live registry and AEAT live-oracle replay.
  1. Step 7.3 — Run the casilla-graph downstream consumers (cuota
     liquida, cuota incrementada) end-to-end against AEAT for the
     baseline employee profile.
  1. Step 7.4 — Update the audit-concerns plan to reflect this
     stream's closure.

## Parallelization

The six per-year phases are mostly independent — each year touches a
different `[revisions."{Y}"]` block in the same TOML and removes one
entry from the same Python allow-list. Per-year phases can be
parallelised across multiple agents IF the agents agree to merge in
strict ID order to avoid TOML-section conflicts. Within a phase, the
0528 and 0530 formula additions can be a single edit.

Phase 1 (2020) is the foundation slice — it must land first because
it validates the implementation pattern against AEAT's live oracle.
Phases 2-6 follow in any order. Phase 7 must run last.

## Verification

Mission success is measured by all of:

1. The orphan-detection gate (`test_no_orphan_parameters_in_any_revision`)
   passes with `_PRE_STAGED_PARAMETERS` shrunk to its empty / only-
   autonomic-pending state.
2. The workbook-parity test for Modelo 100 cuota integra estatal
   (existing) confirms the new `lookup_bracket` formulas match the
   AEAT-published workbook arithmetic to the cent for every
   ejercicio in scope.
3. The Renta WEB Open live-oracle replay (existing) emits the same
   0528 and 0530 values as the registry computes, for the baseline
   employee profile across every ejercicio in scope.
4. Downstream consumers (0532 = 0528 - 0530, 0545 = 0532 + 0540) emit
   correct values. Tests covering those targets continue to pass.

These four gates together prove the chain is computed end-to-end from
the bracket schedule to the cuota integra estatal target with
external authority backing every step. Tests cannot be cheated
because (1) the bracket data is committed and reviewable, (2) the
arithmetic is exercised against AEAT's own outputs, and (3) the
downstream chain links are pre-existing committed formulas.
