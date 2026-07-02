---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S20'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-modelo-surface with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Declare the named generic-module allowlist so a new per-modelo branch in a generic module fails the gate unless the allowlist is consciously extended and ## Scope

- `src/aeat/tests/test_generic_module_modelo_carveouts.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare the named generic-module allowlist so a new per-modelo branch in a generic module fails the gate unless the allowlist is consciously extended

## Scope

- `src/aeat/tests/test_generic_module_modelo_carveouts.py`

## Description

- Declare the named generic-module allowlist as `_RATCHET_BASELINE`; document the deliberate exclusion of the churned domain `_formula_runtime.py` (ADR-permitted `_evaluate_m###_*` op evaluators) and of modelo-keyed DATA modules.

## Outcome

A new per-modelo branch in a scanned generic module fails the gate unless the baseline is consciously lowered; the scope exclusions are documented, not silent. Commit `892faa383`.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
