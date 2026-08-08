---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:7b4780273ee02ce57086b60532429cfd45cca5f90abad6cb9791c4931504b01d'
step_id: 'S287'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S287 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Thread the field selection S277 gave the compiler through to the production text reader, since build_text_field_extraction_prompt calls render_invoice_extraction_prompt with values only and TextInvoiceFieldExtractor._build_request calls it with evidence_text and values only - so no production call site passes fields and W04.P10.S82's fewer-fields arm is still not reachable through the shipped entry point and ## Scope

- `src/cadrumo/llm/_evidence_draft_text.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Thread the field selection S277 gave the compiler through to the production text reader, since build_text_field_extraction_prompt calls render_invoice_extraction_prompt with values only and TextInvoiceFieldExtractor._build_request calls it with evidence_text and values only - so no production call site passes fields and W04.P10.S82's fewer-fields arm is still not reachable through the shipped entry point

## Scope

- `src/cadrumo/llm/_evidence_draft_text.py`

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
