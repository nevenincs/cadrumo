---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S15'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace silent-zero-base-aggregation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-06-19-silent-zero-base-aggregation-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The add an import-deducible casilla to M390 (box, locale, manifest, extraction) and bind it to `ledger_iva_aggregation` import deducible, then add it to the cuota-deducible-total formula so the annual result stops over-stating the importer's amount to pay and ## Scope

- `src/aeat/_data/registry/aeat/modelos/390/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add an import-deducible casilla to M390 (box, locale, manifest, extraction) and bind it to `ledger_iva_aggregation` import deducible, then add it to the cuota-deducible-total formula so the annual result stops over-stating the importer's amount to pay

## Scope

- `src/aeat/_data/registry/aeat/modelos/390/`

## Description

Closed the M390 annual import-deducible silent zero so the annual resultado stops
over-stating an importer's amount to pay. The M390 `cuota-deducible-total`
previously summed only interior soportado and intra-community autorepercutido,
omitting import deducible (the resultado uses the ledger cuotas, not the
reconciliacion-303 cross-check).

- Add internal casilla `iva.anual.soportado.importaciones` (bound, no fichero
  export — M390 does not fichero-export), grounded in LIVA art. 17 + art. 92.
- Add binding `modelo-390-iva-soportado-importaciones-cuota` mirroring the M303
  import binding: `ledger_iva_aggregation`, category `import_third_country`, flow
  `soportado`, fact `iva_amount_sum`.
- Add the casilla to the `modelo-390-iva-anual-cuota-deducible-total` formula.
- Add it to the M390 completeness manifest and the construct (casillas + bindings),
  and add LIVA art. 17 to the construct legal_refs so the coverage check holds.
- Update the M390 registry binding-set assertion to include the new binding.

Modified files:

- `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/casillas/0001-casillas.toml`
- `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/bindings/0001-bindings.toml`
- `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/formulas/0001-formulas.toml`
- `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/completeness_manifest/0001-completeness_manifest.toml`
- `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/constructs/0001-constructs.toml`
- `src/aeat/domain/calculations/registry/tests/test_modelo_390_registry.py`

## Outcome

Registry loads; the M390 deducible total now includes import deducible. Gates
green: `test_modelo_390_registry` (12 passed) and the M390 surface in the registry
sweep (3240 passed overall). The scope note "box, locale, extraction" in the Step
row was over-specified: M390 does not fichero-export and has no locale-parity gate,
so the casilla is internal and needs neither an export offset nor localized labels
— the resultado correction is complete without them.

## Notes

Two unrelated red gates in the full sweep are peer-owned, not this Step:
`test_record_design` manifest drift is the peer's in-flight M303 base bindings
(uncommitted), and `test_tautology_gate` flags `test_iva_wallet_engine_integration.py`
(a peer file this Step never touched; it passed in earlier same-session sweeps, so a
peer introduced the hand-summed assertions). S16 (the reconciliation-divergence
predicate) remains open as an additional guard.
