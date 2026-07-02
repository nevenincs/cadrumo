---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S15'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace fichero-boe-parity-gate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Add an offline fichero-BOE parity test asserting required-applicable casillas reach disk across export-capable covered modelos and ## Scope

- `src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add an offline fichero-BOE parity test asserting required-applicable casillas reach disk across export-capable covered modelos

## Scope

- `src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py`

## Description

- Add `test_fichero_boe_completeness_parity.py`: parametrized over the fixed-width covered modelos with a manifest and a reusable complete draft (130, 111, 115, 123), asserting `required_applicable ⊆ rendered` (every required, representable casilla reaches disk) and that the complete draft exports clean.

## Outcome

Landed in commit `e616666ad`. Eight tests pass (four modelos x two assertions). Also asserts `required_applicable` is non-empty per modelo, so the gate cannot pass vacuously.

## Notes

Modelos 303/200 have manifests but no reusable complete-draft builder in the shared support module; the four covered here plus the 303 suppression case (P02) and the 130 drift case (P03) exercise the gate across the representative shapes.
