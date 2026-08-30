---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:95f8345d4caa072c0af39872f3306a9052f2734a40aa2af16ccc4dc74264da6c'
step_id: 'S64'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Modelo 184's record-type discriminator is blank-capable, and the fix is BLOCKED for the 2025 revision by AEAT's own cell text. PARTIALLY LANDED 2026-08-28. THE DEFECT: `tipo2.tipo-hoja` and `tipo3.tipo-hoja` at wire position 76 are input_kind=manual, required=False, with no formula, binding or constraints, while the diseno states `Constante "E".` on the rentas record and `Constante "S".` on the socio record. A blank at 76 leaves the record type INDETERMINATE in the filed file. It is also why the two Tipo-2 sheets tie: `m184-entidad` and `m184-socio` declare IDENTICAL literals at (1,1) and (2,3), so position 76 is the only thing that could tell them apart. THE REMEDY IS THE OPPOSITE OF M720'S and that is not a contradiction: M720's layout is binding-derived and three tests pin that it must represent every casilla through a binding, which is why it needed a new source kind; M184's generated records ALREADY declare six inline literals, so `kind = "literal"` in the generator mapping is the native expression there. The same defect shape can need opposite remedies, decided by each layout's own contract. WHAT LANDED: the 2023-2024 pair, in `dev/registry/mappings/modelo_184/2023/{0003-entidad,0004-socio}.toml`, whose cells read plainly `Constante "E".` and `Constante "S".`. WHAT IS BLOCKED: the 2025-y-siguientes pair. The generator refused `m184-2025.entidad.f008` with 'ambiguous official constant content' -- its cell reads `Constante "E". rentas. Declaracion anual.`, the constant merged with descriptive prose, which none of the extractor's patterns parse. THAT REFUSAL IS CORRECT AND MUST NOT BE ROUTED AROUND: the generator does not accept a declared literal, it DERIVES the value from AEAT's own text and compares bytes, which is the never-invent-a-figure rule mechanised. Widening the extractor to accept a constant followed by arbitrary prose is the widen-a-matcher hazard, on a matcher guarding a filing byte. The 2025 socio entry was reverted alongside it: a revision with one record guaranteed and the other blank-capable is a worse state to review than one uniformly unfixed. TWO THINGS STILL OPEN. First, the 2025 cell needs either a grounded correction mechanism for merged constant-plus-prose content or an operator ruling on its reading. Second, and measured: the mapping change does NOT close the join even where it lands -- all four Tipo-2 sheets still fail to join, so the tie needs something beyond declared constants; `dev/registry/mappings/modelo_184 and dev/registry/pipeline/_export_tree.py`.

## Scope

- `dev/registry/mappings/modelo_184 and dev/registry/pipeline/_export_tree.py`

## Changes

- `M` `dev/registry/pipeline/_export_tree.py`
- `M` `dev/registry/tests/test_export_tree.py`
- `M` `dev/registry/tests/test_generated_export_trees.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/casillas/ctipo2.tipo-hoja__ctipo3.rendimiento-neto-minorado-agricola-eo.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/export/0002-record-m184-entidad.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/export/0004-record-m184-socio.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/casillas/ctipo2.tipo-hoja__ctipo3.rendimiento-neto-minorado-agricola-eo.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/export/0002-record-m184-entidad.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/export/0004-record-m184-socio.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/export/_generation.provenance.json`
- `verify:` `uv run --no-sync pytest -n 0 -q dev/registry/tests/test_generated_export_trees.py -k m184` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/registry/pipeline/_export_tree.py dev/registry/tests/test_export_tree.py dev/registry/tests/test_generated_export_trees.py` -> `pass`

## Notes

- The four f008 mapping literal declarations were verified predecessor work in `fd4b91e2f3f5ada31ebcd1a5a100d8e280a3972c`; this step neither authored nor restates them.
- The exact export-ref reconciliation and rollback-journal cleanup were verified predecessor work in `1b937634c3869104679e2a6f18263819833ad794`; this step consumes their generated-publication behaviour without claiming those paths.
