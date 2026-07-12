---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S21'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Rename product logical storage namespaces without touching authority field names and ## Scope

- `src/cadrumo persistence namespace registry/repository and cohesive consumers/tests/examples` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename product logical storage namespaces without touching authority field names

## Scope

- `src/cadrumo persistence namespace registry/repository and cohesive consumers/tests/examples`

## Description

- Rename all 67 registered logical storage namespaces and owners to the Cadrumo product prefixes.
- Preserve the six internal `.aeat.` authority segments that identify the external tax authority.
- Reject former product namespaces centrally before namespace-scoped read, write, delete, list, and batch operations.
- Update cohesive runtime consumers and real-behavior storage tests.

## Outcome

- Cut over 61 ordinary registry rows and six mixed-authority rows without compatibility aliases or fallback paths.
- Added a single former-product-prefix admission boundary with explicit validation context.
- Verified five focused tests in an isolated filesystem mirror, covering the 67-row invariant, refusal without storage mutation, and batch behavior.

## Notes

- A broader 29-test mirror probe produced 28 passes and one unchanged pre-existing discovery assertion failure for `cadrumo.domain.transactions.bucket`; the focused S21 proof passes.
- The mirror setup reported a missing optional `.env.example`; this did not affect the test run.
