---
step_id: "W12.P65.S216"
date: 2026-05-30
modified: '2026-05-30'
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W12.P65.S216

## Step

Extend M303 closure formula DAG with boxes 64 (suma de resultados), 66 (atribuible Estado), corrected box 69 (66+77+68-78), and box 71 (resultado final = 69-70+109) per Orden HAC/819/2024 art. 1 §§4-6; add legal ref `orden-hac-819-2024:art-1` and corpus HTML; update casillas input_kind from manual to computed; regenerate 16 corpus PDFs; add 32 VERIFIED engine-recomputes tests for all 4 closure boxes (tasklist #88).

## Outcome

VERIFIED - all 32 new engine-recomputes tests pass for all 8 new-template specimens (2023-2024) across all 4 closure boxes. M303 closure DAG extended from FORMULA-MISMATCH to VERIFIED for boxes 64, 66, 69, and 71.

## Changes

### Registry TOML

`src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`

- Added formula `modelo-303-iva-suma-resultados` targeting box 64: `c46 + c58 + c76` (Orden HAC/819/2024 art. 1 §4).
- Added formula `modelo-303-iva-atribuible-estado` targeting box 66: `(c64 * c65) / 100` (Orden HAC/819/2024 art. 1 §4, RD 1624/1992 art. 71).
- Updated formula `modelo-303-iva-resultado` targeting `iva.resultado` (box 69): corrected from `c46 - c78` to `(c66 + c77 + c68) - c78` (Orden HAC/819/2024 art. 1 §5).
- Added formula `modelo-303-iva-resultado-final` targeting box 71: `(iva.resultado - c70) + c109` (Orden HAC/819/2024 art. 1 §6).
- Updated construct `modelo-303-iva-autoliquidacion`: added casillas 58, 76, 64, 65, 66, 77, 68, 70, 109, 71 and updated legal_refs to include `orden-hac-819-2024:art-1`, `ley-37-1992:art-94/122/123/124`.
- Updated `verification_expectations.computed_casillas` to include "64", "66", "71".

`src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.toml`

- Box 64: `input_kind = "manual"` -> `"computed"`, added `formula = "modelo-303-iva-suma-resultados"`.
- Box 66: `input_kind = "manual"` -> `"computed"`, added `formula = "modelo-303-iva-atribuible-estado"`.
- Box 69 (iva.resultado): updated label to reflect correct formula `[46]+[58]+[76]=[64]`, `[64]*[65]/100=[66]`, `[66]+[77]+[68]-[78]=[69]`.
- Box 71: `input_kind = "manual"` -> `"computed"`, added `formula = "modelo-303-iva-resultado-final"`.

### Legal catalogue

`src/aeat/_data/registry/aeat/legal/iva.toml`

- Added entry `[legal."orden-hac-819-2024:art-1"]` with evidence_tier `legal_authority`, BOE reference `BOE-A-2024-6840`, corpus_ref pointing to the new HTML file, published_at `2024-04-09`, effective_from `2024-04-10`.

`src/aeat/_data/corpus/normatives/html/orden-hac-819-2024-art-1.html`

- NEW FILE -- HTML corpus content for Orden HAC/819/2024 Articulo 1, sourced from AEAT BOE publication, containing the normative text for M303 boxes 64/65/66/69/71.

### Fixture generator

`src/aeat/tests/fixtures/justificantes/_generate.py`

- Updated `_Modelo303CorpusFixture` dataclass: added fields `c64`, `c66`, `c71`.
- Updated `_compute_m303_closure` to return 5-tuple `(c46, c64, c66, c69, c71)`; all auxiliary boxes zero in the simple corpus case so `c64 == c46`, `c66 == c64`, `c69 == c66`, `c71 == c69`.
- Updated all 15 fixture instantiations to unpack the 5-tuple.
- Updated `_draw_modelo_303_corpus` to use `fixture.c64`, `fixture.c66`, and `fixture.c71` for boxes 64, 66, and 71 respectively.

### Corpus PDFs

`src/aeat/tests/fixtures/justificantes/303/`

- Regenerated all 16 M303 corpus PDFs (8 new-template 2023-2024, 8 legacy 2021-2022) with formula-consistent values for the new closure boxes.

### Verification tests

`src/aeat/adapters/inbound/declaracion/test_verification_chain.py`

- Updated `_COMPUTED_CASILLAS_M303` frozenset to include "64", "66", "71".
- Added `inputs["65"] = Decimal("100")` in the existing `test_verification_chain_m303_engine_recomputes_resultado_regimen_general` to supply the territorio-comun apportionment percentage.
- Extracted shared helper `_build_m303_engine_result` to avoid 4x repetition of parse + engine call logic.
- Added `_M303_NEW_TEMPLATE_PARAMS` parametrize list (8 specimens 2023-2024).
- Added 4 new test functions (8 parametrize variants each = 32 new tests total):
  - `test_verification_chain_m303_engine_recomputes_box_64_suma_resultados` - VERIFIED
  - `test_verification_chain_m303_engine_recomputes_box_66_atribuible_estado` - VERIFIED
  - `test_verification_chain_m303_engine_recomputes_box_69_resultado_autoliquidacion` - VERIFIED
  - `test_verification_chain_m303_engine_recomputes_box_71_resultado_final` - VERIFIED

## Gate results

- Registry validation: passes (all legal_refs resolve, constructs cover component refs, computed casilla set consistent).
- 32 new VERIFIED tests: all pass for all 8 specimens (2023-1T through 2024-4T).
- Pre-existing M131 failures (2 tests using `año_override=2026` vs detected 2024) remain from commit `7ab224117` -- not caused by this step.
- Registry calculation suite: passes clean.
