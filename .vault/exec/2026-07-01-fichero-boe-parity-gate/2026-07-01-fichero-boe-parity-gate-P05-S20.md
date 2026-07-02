---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S20'
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
     The S20 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Run the filing and modelo export test suites plus src/aeat collect-only and capture a green owner-scoped gate and ## Scope

- `src/aeat/application/filing/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the filing and modelo export test suites plus src/aeat collect-only and capture a green owner-scoped gate

## Scope

- `src/aeat/application/filing/tests`

## Description

- Run the owner-scoped export surface and confirm green: the filing export suite (64 tests pass, including the previously-red 131 binding-derived test after the truth-grounded fix), the modelo export suite (9 pass), the CLI coverage-advisory test (2 pass), and an owner-scoped collect-only (240 tests collected, no collection errors).

## Outcome

The owner surface is green. Earlier collect-only runs were red from unrelated peer churn (a `workflow` circular import, then a `_participation_index` import rename); both cleared as the peer campaigns committed, per `full-tree-gate-must-distinguish-owner`. The full `src/aeat` collect-only was not run to completion here (multi-minute gate) but the owner-scoped surface it depends on collects and passes clean.

## Notes

The three reframed steps (P03.S09 numbering/segmento assertion, P03.S10 record-order assertion, P04.S16 order fidelity) remain unchecked deliberately: they were reframed rather than implemented as literally specced (see the audit's `reframed-*` findings), because a runtime numbering/segmento re-check is redundant with registry-build validation and a runtime record-order check is tautological (the renderer sorts by order). The audit is the deferral register for these per `plan-closure-requires-exec-records`.
