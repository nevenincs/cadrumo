---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0e55fa207967cdcff44f32b6e4bd101b30bcac96ba02bb387a0bb6974e5932f3'
step_id: 'S262'
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
     The S262 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Map each Facturae InvoiceTotals element onto the right term of the codebase identity, since NO Facturae element equals the codebase total and it has to be derived rather than read. Measured against the real parser at HEAD on a specimen built to the schema's own documented arithmetic: a Facturae invoice carrying the ordinary 15 percent IRPF retencion states InvoiceTotal already NET of it, the parser reads that element as grand_total, and the parser recovers no retencion at all, so the closure identity computes 242.00 against a stated 212.00 and exceeds it by exactly the 30.00 retencion. That is a false CLOSURE_DISCREPANCY blocking a correct invoice, live today, on the commonest Spanish professional document there is. Two arms. Retencion is the live one. Suplidos is the second and is NOT what was first reported: reimbursable expenses enter at TotalExecutableAmount and never at InvoiceTotal, so the originally rowed mechanism was wrong and the term simply has no producer. Both corpus specimens are blind to this because both are synthetic and carry neither optional term, which is a fixture-provenance instance in its own right. Blocked on one artefact: the InvoiceTotals element sequence and its four computation annotations bundled as extracted fact with a provenance stamp naming the OFFICIAL source URL, schema version, retrieval date and payload SHA-256, on the precedent of the bundled Facturae country enumeration. The text currently in hand came from a third-party mirror and must be verified against facturae.gob.es before it grounds anything and ## Scope

- `src/cadrumo/adapters/inbound/einvoice` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Map each Facturae InvoiceTotals element onto the right term of the codebase identity, since NO Facturae element equals the codebase total and it has to be derived rather than read. Measured against the real parser at HEAD on a specimen built to the schema's own documented arithmetic: a Facturae invoice carrying the ordinary 15 percent IRPF retencion states InvoiceTotal already NET of it, the parser reads that element as grand_total, and the parser recovers no retencion at all, so the closure identity computes 242.00 against a stated 212.00 and exceeds it by exactly the 30.00 retencion. That is a false CLOSURE_DISCREPANCY blocking a correct invoice, live today, on the commonest Spanish professional document there is. Two arms. Retencion is the live one. Suplidos is the second and is NOT what was first reported: reimbursable expenses enter at TotalExecutableAmount and never at InvoiceTotal, so the originally rowed mechanism was wrong and the term simply has no producer. Both corpus specimens are blind to this because both are synthetic and carry neither optional term, which is a fixture-provenance instance in its own right. Blocked on one artefact: the InvoiceTotals element sequence and its four computation annotations bundled as extracted fact with a provenance stamp naming the OFFICIAL source URL, schema version, retrieval date and payload SHA-256, on the precedent of the bundled Facturae country enumeration. The text currently in hand came from a third-party mirror and must be verified against facturae.gob.es before it grounds anything

## Scope

- `src/cadrumo/adapters/inbound/einvoice`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Executed. Verified against HEAD: the Facturae InvoiceTotals composition is a bundled corpus artefact carrying its own provenance, mapping each element onto the right term of the codebase identity.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
