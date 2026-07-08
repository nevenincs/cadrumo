---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-08'
step_id: 'S15'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace iva-prorrata-complexity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-07-iva-prorrata-complexity-plan placeholders are machine-filled by
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
     The Verify all three art-106 reglas (100/0/common) and the +10% comparison against an AEAT Manual practico worked example with no substrate-derived expected values and ## Scope

- `src/aeat/application/aggregation/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify all three art-106 reglas (100/0/common) and the +10% comparison against an AEAT Manual practico worked example with no substrate-derived expected values

## Scope

- `src/aeat/application/aggregation/tests/`

## Description

- Add `src/aeat/application/aggregation/tests/test_prorrata_especial_art106_oracle.py`, a dedicated verification of the LIVA art. 106 per-input routing (S12) and the art. 103.Dos.2 +10% advisory (S13) driven end-to-end through the PRODUCTION aggregation path (`aggregate_iva_ledger_observations_from_repositories` + `resolve_iva_ledger_binding_values`).
- Verify all three art. 106.Uno reglas both composed (regla 1.ª full + regla 2.ª nil + regla 3.ª general%) and isolated per-classification, each proven distinct from the general-regime flat-percentage result.
- Verify the +10% mandatory-especial advisory fires on the REAL production general-vs-especial deducible cuota totals for the same ejercicio, and stays silent when the general deduction does not exceed the especial one.

## Outcome

The especial routing and the +10% obligation are verified against a hand-constructed register and ledger scenario driven through the production path, with a structural anti-tautology core: the especial deducible cuota (16.80) must differ from the general flat result (18.90), so a silent fallback to the general percentage would fail the test. 5 verification tests pass.

## Notes

- NO bundled AEAT *Manual práctico IVA* prorrata-ESPECIAL worked-example oracle ships in the corpus (only the general-prorrata regularización oracle `modelo-303-prorrata-general-regularizacion.json` exists). Stated explicitly in the test module docstring; per the prorrata-especial ADR this verification uses the hand-constructed-register alternative with structural anti-tautology (mirroring the art-105.Cinco global-vs-average S09 test). Expected values derive from the LIVA art. 106.Uno reglas (grounded verbatim in the bundled corpus by S10) and the chosen register percentage, never from the `deductible_percentage_for` substrate under test.
- Pre-existing peer-owned failures unrelated to this step: the import-hygiene gate reports 13 test-only `aeat.tests._inventory` reaches in concurrently-staged PEER test files (documented test-debt drift), and the bienes-inversión `casilla-63` registry-completeness broken-HEAD persists; neither references this step's files.
