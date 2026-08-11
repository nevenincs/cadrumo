---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a095daed59e7d090bc38ef4e82ba66ce3bfc35e0c9317bb6085e8c33bff009fd'
step_id: 'S218'
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
     The S218 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Drive the ingestion category gate through the READER rather than a literal status, since every case in it supplies counterparty_country_status directly while production computes it from the draft field the structured reader populates. That is why the vocabulary sparing shipped proven-in-logic and unreachable-in-wiring: a literal TH spares, while a TH read from a UBL document arrives as None and refuses. The gate is green and the defect is invisible to it. Add cases that build the document, run the real reader, and assert the resolver outcome, so the wiring is pinned and not only the logic. Depends on S178 removing the collapse, and is the assertion that will prove S178 landed where it matters rather than merely emitting an envelope and ## Scope

- `src/cadrumo/application/ledger` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Drive the ingestion category gate through the READER rather than a literal status, since every case in it supplies counterparty_country_status directly while production computes it from the draft field the structured reader populates. That is why the vocabulary sparing shipped proven-in-logic and unreachable-in-wiring: a literal TH spares, while a TH read from a UBL document arrives as None and refuses. The gate is green and the defect is invisible to it. Add cases that build the document, run the real reader, and assert the resolver outcome, so the wiring is pinned and not only the logic. Depends on S178 removing the collapse, and is the assertion that will prove S178 landed where it matters rather than merely emitting an envelope

## Scope

- `src/cadrumo/application/ledger`

## Description

- Read the ingestion category gate for how each case obtains the counterparty
  country status, rather than trusting the row account of it.
- Run both the category-resolution and structured-degradation suites.

## Outcome

PREMISE EXPIRED, delivered at HEAD. The reader-driven cases the row asks for
exist: they write a UBL document, add it through the real evidence service,
run the real extractor, and derive the counterparty status from the DRAFT
FIELD the reader populated rather than from a literal.

That is exactly the wiring the row said was unpinned, and the dependency it
named as blocking -- the collapse being removed so a stated token reaches the
resolver at all -- has landed with it. The suites carry sixty passing cases
between them.

The non-vacuity the row would have wanted is present too, and independently:
an anchor class asserts the probe token is still uncatalogued in the bundled
vocabulary, so a vocabulary change that catalogued it would fail loudly rather
than turning every degradation case green for the wrong reason.

No change made. Closed on the measurement.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

One case in that suite is worth carrying forward because it guards the
under-declaration direction rather than the over-refusal one the row was
about: the filer own residency gap is never forgiven by the counterparty
excuse. An unscoped exemption had suppressed the refusal for every outstanding
residency once the counterparty code happened to be uncatalogued, which would
have honoured a zero-rated export with neither party established.
