---
tags:
  - '#reference'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---



# `m303-form-vs-semantic-casilla-dual-keying` reference: `M303 official box to semantic source projection map`

The authoritative, label-cross-checked Stage-2 projection map. Each in-scope
official Diseno-de-Registros numbered cuota box is paired with the single
already-computed semantic casilla id it copies. Every box flips from
`input_kind = "manual"` to `input_kind = "computed"` and gains a single-leaf
`FormulaDefinition` (`modelo-303-dr303-NN-projection`) whose expression is the
one semantic casilla-id leaf, resolved by the existing `_evaluate_leaf`
primitive in `src/aeat/domain/calculations/registry/_formula_runtime.py` and
ordered topologically by `formula_evaluation_order` in
`src/aeat/domain/calculations/registry/_runtime_graph.py`. No box is wired
without an exact 1:1 label match; the box's own `legal_refs` are copied verbatim
onto its projection formula.

Cross-checked read-only on 2026-06-13 against
`src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
and `.part-002.toml`.

## Summary

### Projection map (box -> single semantic source)

Each row: official box id, the box's own label, the semantic source id, the
source's own label, and the box's existing `legal_refs` (copied verbatim onto
the projection formula). Boxes 09/06/03/11/13/27 live in part-001 (09-13) and
part-002 (27); 29/33/37/45 live in part-002.

| Box | Box label | Semantic source id | Source label fragment | Box legal_refs (verbatim) |
| --- | --- | --- | --- | --- |
| `09` | IVA devengado RG tipo general 21pct - Cuota | `iva.repercutido.general` | Cuota IVA repercutido al tipo general (21%) | `ley-37-1992:art-88`, `ley-37-1992:art-90`, `ley-37-1992:art-91`, `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1` |
| `06` | IVA devengado RG tipo reducido 10pct - Cuota | `iva.repercutido.reducido` | Cuota IVA repercutido al tipo reducido (10%) | `ley-37-1992:art-88`, `ley-37-1992:art-90`, `ley-37-1992:art-91`, `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1` |
| `03` | IVA devengado RG tipo super-reducido 4pct - Cuota | `iva.repercutido.super-reducido` | Cuota IVA repercutido al tipo super-reducido (4%) | `ley-37-1992:art-88`, `ley-37-1992:art-90`, `ley-37-1992:art-91`, `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1` |
| `11` | IVA devengado adquisiciones intracomunitarias bienes y servicios - Cuota | `iva.autorepercutido.intracomunitaria.devengado` | ...devengada en adquisiciones intracomunitarias... oficial casillas 10/11 | `ley-37-1992:art-88`, `ley-37-1992:art-90`, `ley-37-1992:art-91`, `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1` |
| `13` | IVA devengado otras ops inversion sujeto pasivo excl intracom - Cuota | `iva.autorepercutido.interior.devengado` | ...operaciones interiores con inversion del sujeto pasivo... oficial casilla 13 | `ley-37-1992:art-88`, `ley-37-1992:art-90`, `ley-37-1992:art-91`, `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1` |
| `27` | Total cuota devengada | `iva.cuota-devengada-total` | Total cuota IVA devengada | `ley-37-1992:art-88`, `ley-37-1992:art-90`, `ley-37-1992:art-91`, `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1` |
| `29` | IVA deducible ops interiores corrientes - Cuota | `iva.soportado.interiores` | Cuota IVA soportado en operaciones interiores corrientes | `ley-37-1992:art-92`, `ley-37-1992:art-94`, `ley-37-1992:art-95`, `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1` |
| `33` | IVA deducible importaciones bienes corrientes - Cuota | `iva.soportado.importaciones` | ...soportado deducible en importaciones de bienes corrientes... oficial casilla 33 | `ley-37-1992:art-92`, `ley-37-1992:art-94`, `ley-37-1992:art-95`, `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1` |
| `37` | IVA deducible adquisiciones intracomunitarias corrientes - Cuota | `iva.autorepercutido.intracomunitaria.deducible` | ...deducible autorepercutida en adquisiciones intracomunitarias... oficial casillas 36/37 | `ley-37-1992:art-92`, `ley-37-1992:art-94`, `ley-37-1992:art-95`, `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1` |
| `45` | Total a deducir - Cuota | `iva.cuota-deducible-total` | Total cuota IVA deducible | `ley-37-1992:art-92`, `ley-37-1992:art-94`, `ley-37-1992:art-95`, `rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1` |

Note: the box `legal_refs` (art. 90/91 for devengado, art. 94/95 for deducible)
are the box rows' own grounding copied verbatim per
`registry-calculation-legal-grounding` and the ADR's directive to copy each
box's existing refs, NOT rewritten to match the narrower ADR prose (art. 88 /
art. 92 only). The projection formula carries the box's refs verbatim.

### Box 37 collision resolution (pinned, NOT deferred)

The registry self-labels TWO casillas as "casilla 37":

- `iva.autorepercutido.interior.deducible` -- label "Cuota IVA deducible
  autorepercutida en operaciones interiores con inversion del sujeto pasivo
  (LIVA art 84.Uno.2 + art 92; oficial casilla 37)". This is the **interior**
  reverse-charge deducible leg.
- `iva.autorepercutido.intracomunitaria.deducible` -- label "Cuota IVA deducible
  autorepercutida en adquisiciones intracomunitarias (LIVA art 13 + art 15 +
  art 84.Uno.2 + art 92; oficial casillas 36/37)". This is the **AIC**
  (adquisiciones intracomunitarias) deducible leg.

Box `37`'s own label is "IVA deducible adquisiciones intracomunitarias
corrientes - Cuota" -- the **adquisiciones intracomunitarias** leg. The
label-exact match is therefore `iva.autorepercutido.intracomunitaria.deducible`.
This matches the 2026-06-13 ADR ratification (Open Question 2) verbatim and the
2026-06-09 IVA routing decisions (the AIC deducible cuota is the box-37 leg; the
interior reverse-charge deducible cuota is box-37's sibling that the registry
self-documents as "oficial casilla 37" only because the official form folds both
inversion-del-sujeto-pasivo legs into the same printed position). The label is
unambiguous; box `37` is **wired to `iva.autorepercutido.intracomunitaria.deducible`**,
not deferred.

### Boxes that REMAIN manual (Stage-2 out of scope)

Per the ratified selective scope, these stay `input_kind = "manual"` and are NOT
populated by projection:

- **Base boxes** (`01`, `04`, `07`, `10`, `12`, `28`, `30`, `32`, `34`, `36`,
  `38`, ...) -- no ledger-derived semantic cuota source.
- **Tipo (percentage) boxes** (`02`, `05`, `08`, `17`, `20`, `23`, ...) -- no
  semantic equivalent.
- **Recargo de equivalencia** boxes (`16`-`26`, `156`-`170`) and the **new-tipo
  tier** boxes (`150`-`155`, `165`-`170`) -- no ledger source in the current
  engine.
- **Regimen simplificado** boxes (`47` onward).
- **Informativa / resultado** boxes already manual or already
  computed/bound (`46`/`64`/`65`/`66`/`69`/`71` are out of scope -- already carry
  value; `59`/`60`/`68`/`70`/`76`/`77`/`108`-`124` stay manual).

### Advisory-narrowing consequence (honest)

After Stage-2 every constituent in BOTH Stage-1 `implies_any_nonzero` advisory
predicates becomes a computed projection:

- Devengado predicate constituents `03`/`06`/`09`/`11`/`13` -- ALL flipped to
  computed.
- Deducible predicate constituents `29`/`33`/`37` -- ALL flipped to computed
  (box `37` wired, not deferred).

Because NO manual cuota box remains in either constituent list, both Stage-1
`implies_any_nonzero` ADVISORY predicates are satisfied by construction (the
antecedent-positive -> consequent-positive implication holds whenever the
semantic total is positive, since the projection copies the same value). They
are therefore **retired** (removed), not narrowed-and-retained, to avoid leaving
a dead always-green predicate. The calculate-path advisory in
`_official_box_advisory.py` reads the same predicates as its single source of
truth, so retiring the predicates narrows the calculate advisory in lock-step.
The per-box equality consistency predicates (new `equals` operator) replace them
as the live verify-gate guard, catching a future mis-edit (a box re-flipped to
manual, or a projection pointed at the wrong source).
