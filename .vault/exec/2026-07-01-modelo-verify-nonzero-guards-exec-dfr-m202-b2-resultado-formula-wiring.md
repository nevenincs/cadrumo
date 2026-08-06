---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-07-01'
modified: '2026-07-31'
body_hash: 'sha256:4189483a312f3a0741d2f8157393d0cc305a635da4f3cba24c21966cf6ff8231'
related:
  - "[[2026-07-01-modelo-verify-nonzero-guards-m202-deferred-items-audit]]"
  - "[[2026-07-01-modelo-verify-nonzero-guards-review-closeout-audit]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# M202 B2 resultado previo formula-wiring deferral resolution

This record resolves the documented deferral
`DFR-M202-B2-RESULTADO-FORMULA-WIRING`, cross-referenced from
`2026-07-01-modelo-verify-nonzero-guards-m202-deferred-items-audit.md`
finding `m202-b2-resultado-previo-unwired` (critical) and from
`2026-07-01-modelo-verify-nonzero-guards-review-closeout-audit.md`. The audit
found that casilla `26` (Mod. 40.3 LIS B2 "casos especificos" resultado
previo) was consumed by no formula in any of the three M202 revisions: the
`modalidad-40-3-resultado` formula (target casilla `32`, which feeds
`cantidad-a-ingresar` via `34 = max(32, 33)`) read only casilla `18` (the B1
"caso general" resultado previo), byte-identical across `2019-2022`,
`2023-2024`, and `2025-y-siguientes`. This was a suspected
formula-correctness defect deliberately left unpatched pending authoritative
AEAT verification, per `aeat-safety-legal-gates` and
`no-tautological-calculation-tests`.

## Description

- Read the M202 `2025-y-siguientes` registry tree in full (casillas `16`-`34`,
  `61`-`66`; formulas `0005`/`0006`/`0013`; the `modelo-202-foundation`
  construct; the `modelo-202-fichero-boe` page-02 export layout) to confirm
  casilla `26`'s formula (`22+25+63+66+50-42+51-52`) and casilla `32`'s prior
  formula (`percent(18-27-28, 29) - 30 - 31`).
- Verified the export layout: claves `18` and `26` are two independent,
  optionally-populated fixed-width fields with no lane-discriminator flag
  between them, confirming the registry's own DR shape carries no B1-vs-B2
  selector to route through.
- Grounded against the bundled authoritative corpus FIRST, per
  `legal-grounding-verifies-bundled-authoritative-corpus`:
  `src/aeat/_data/corpus/aeat_official/instructions/modelo_202/files/modelo-202-instrucciones.html`
  (line 289, 2025+ instructions, `source_ref = "aeat-modelo-202-instructions"`)
  and the sibling `modelo-202-instrucciones-2023-2024.html` (line 240,
  `source_ref = "aeat-modelo-202-instructions-2023-2024"`, covering
  `2019-2022` and `2023-2024`). Both bundled files already state the clave 32
  formula verbatim: "Clave [32] = ( [clave [18] (o clave [26]) - clave [27] -
  clave [28] ] x clave [29]/100 ) - clave [30] - clave [31]."
- Cross-corroborated, as secondary evidence only, against the live AEAT sede
  instructions page for 2025
  (`https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/impuesto-sobre-sociedades/modelo-202-is-i_____resencia-territorio-fraccionado_/instrucciones/Instrucciones-para-2025.html`),
  which repeats the identical formula text and confirms the B1
  ("CASO GENERAL, ENTIDADES CON PORCENTAJE UNICO") / B2 ("CASOS ESPECIFICOS,
  EMPRESAS CON MAS DE UN PORCENTAJE") section framing as mutually exclusive
  alternatives for the same "resultado previo" concept.
- Confirmed no B1-vs-B2 discriminator binding exists anywhere in the M202
  registry tree (no profile fact, no bound casilla) and that both lanes'
  manual inputs default to zero when unfilled, so an additive combination
  (`add(18, 26)`) reproduces the AEAT "18 (o 26)" selection without
  inventing new registry data — the same idiom the registry already uses one
  level down (clave 26 itself sums four optional, usually-only-one-populated
  tipo-lane sub-components).
- Fixed `formulas/0006-*` (`modalidad-40-3-resultado`) in all three revisions
  (`2019-2022`, `2023-2024`, `2025-y-siguientes`): replaced the bare
  `{ casilla_id = "18" }` leaf with
  `{ op = "add", args = [{ casilla_id = "18" }, { casilla_id = "26" }] }`, and
  extended each formula's `source_citations.required_text` with
  `"(o clave [26])"` so the evidence gate cross-checks the new wiring against
  the bundled corpus on every registry load.
- Replaced the prior canary test
  (`test_committed_modelo_202_b2_resultado_previo_remains_unwired_from_modalidad_40_3_resultado`,
  which locked the defect's absence-of-wiring) with two positive regressions
  in `test_modelo_202_registry.py`, parametrized across all three revisions:
  a structural graph-wiring assertion (clave 26 is referenced; the
  combination node is specifically `add(18, 26)`, not `subtract`/`max`) and a
  real-behavior runtime-execution proof via `_evaluate_expression` (claves
  27-31 held at neutral values; clave 18 = 0, clave 26 = 1000; result = 1000,
  not 0) — per `no-tautological-calculation-tests`, this proves the wiring is
  behaviorally live without re-deriving any LIS tax-rate arithmetic.
- Updated the M202 deferred-items audit with a full **Resolution** section
  documenting the grounding, the fix, and the tests.

## Outcome

Confirmed defect, fixed. Casilla 26 (B2 resultado previo) now feeds casilla
32 (modalidad-40-3-resultado) in all three M202 revisions, grounded verbatim
against the bundled AEAT Modelo 202 instructions corpus. No
`implies_nonzero(["26", "32"])`-style advisory was authored: now that clave 26
flows through arithmetically, a genuine zero clave 32 following a nonzero
clave 26 is a legitimate outcome under bonificaciones/retenciones/
territorio-comun adjustments, so no antecedent casilla is a
false-positive-free guard candidate.
Residual risk: this slice does not add a distinct registry validation that
rejects dual-populated B1 and B2 lanes. If an upstream path permits both lanes
to be positive, additive selector semantics would overstate clave 32. That
validation/modeling hardening remains separate from the confirmed formula fix.

## Files

- `src/aeat/_data/registry/aeat/modelos/202/revisions/2019-2022/formulas/0006-modelo-202-2019-2022-modalidad-40-3-resultado.toml`
- `src/aeat/_data/registry/aeat/modelos/202/revisions/2023-2024/formulas/0006-modelo-202-2023-2024-modalidad-40-3-resultado.toml`
- `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/formulas/0006-modelo-202-modalidad-40-3-resultado.toml`
- `src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py`
- `.vault/audit/2026-07-01-modelo-verify-nonzero-guards-m202-deferred-items-audit.md`

## Verification

- Bundled corpus:
  `src/aeat/_data/corpus/aeat_official/instructions/modelo_202/files/modelo-202-instrucciones.html:289`
  and `modelo-202-instrucciones-2023-2024.html:240`.
- Live AEAT sede confirmation, as secondary evidence only:
  `https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/impuesto-sobre-sociedades/modelo-202-is-i_____resencia-territorio-fraccionado_/instrucciones/Instrucciones-para-2025.html`
  (Modelo 202, 2025).
- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py`
  — 18 passed.
- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry -k 202`
  — 1277 passed, 2434 deselected.
- `uv run --no-sync pytest -q src/aeat/domain/calculations`
  — 3683 passed, 27 failed, 1 deselected; every failure is pre-existing and
  unrelated (concurrent "boolean-binding" campaign WIP touching
  `test_selector_shape.py`, `test_authority.py`,
  `test_modelo_100_drift_detection.py`,
  `test_modelo_100_registry_constructs.py`, `test_queries.py`,
  `test_registry_reviewability.py`; confirmed via `git status`/`git diff`
  showing those files carry other agents' uncommitted changes, none of which
  touch M202 or the formula runtime). Per `full-tree-gate-must-distinguish-owner`,
  these failures are out of this deferral's scope and were not modified.
- `uv run --no-sync pytest --collect-only -q src/aeat` — clean collection,
  14345/16592 tests collected, no collection errors.
