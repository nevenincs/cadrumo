---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:57e9db2ecc09c9fb3f66a97d8a98984d133d7a03c50481f91dd9bcebb86b088d'
step_id: 'S22'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace invoice-canonical-structure with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S22 and 2026-08-06-invoice-canonical-structure-plan placeholders are machine-filled by
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
     The Answer whether an invoice-only bucket can reach a filed M390 through the screen gap, tracing the M390 binding set to its value sources and settling whether both sides of the 390-to-303 reconciliation blocking rule derive from the same ledger, and encode the answer as a test rather than as prose and ## Scope

- `src/cadrumo/application/aggregation/tests/test_modelo_bindings.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Answer whether an invoice-only bucket can reach a filed M390 through the screen gap, tracing the M390 binding set to its value sources and settling whether both sides of the 390-to-303 reconciliation blocking rule derive from the same ledger, and encode the answer as a test rather than as prose

## Scope

- `src/cadrumo/application/aggregation/tests/test_modelo_bindings.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
