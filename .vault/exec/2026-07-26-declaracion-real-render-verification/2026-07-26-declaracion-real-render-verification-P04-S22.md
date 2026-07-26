---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S22'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace declaracion-real-render-verification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S22 and 2026-07-26-declaracion-real-render-verification-plan placeholders are machine-filled by
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
     The Measure the ledger evidence text layer against a size-aware segmentation change, the second and more consequential unmeasured consumer since it reads taxpayer financial documents and ## Scope

- `src/cadrumo/application/ledger` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Measure the ledger evidence text layer against a size-aware segmentation change, the second and more consequential unmeasured consumer since it reads taxpayer financial documents

## Scope

- `src/cadrumo/application/ledger`

## Description

- Enumerate the PDFs the ledger evidence text layer actually consumes, with their declared provenance.
- Compare today's extraction against a size-aware variant, page by page, with byte-identity as the pass condition.
- Characterise any change as cosmetic or substantive before concluding.
- Trace what downstream consumes the extracted text.

## Outcome

Measured across nine PDFs: four adversarial synthetics, a scanned invoice, a real ZUGFeRD invoice, and three N26 bank statements.

Thirteen pages of real bank statements are byte-identical. The adversarial and scanned fixtures are identical or unreadable either way. The one real text-native invoice changed on both pages.

The change is bounded and saying only "changed" would overstate it. Character counts are identical at 1203 and 573, no numeric token is lost or gained, and the second page's numeric sequence is unchanged. What moves is line grouping and reading order: a line-item quantity is split onto its own line and a heading relocates.

That is still enough to answer the question as no. The extracted text feeds an invoice draft builder that parses supplier tax id, invoice number, date, taxable base, IVA rate, IVA amount and grand total by label-anchored regex over the text. That is mechanically the same class as the named_label strategy this whole campaign is about, and it depends on a label staying adjacent to its value. A reordering that separates them would silently change a parsed invoice amount. On this specimen the labelled amounts survive, but one specimen is not a licence.

The constraint lands on the mechanism rather than the goal. The probe used extract_text with a size attribute, which splits words on size change and alters line assembly as a side effect. A narrower mechanism, or one scoped to the declaracion entry point rather than the shared primitive, may leave this path byte-identical. That is now a better-posed question than the one the ADR opened with, and is tracked as its own Step.

## Notes

The invoice evidence for this conclusion is n=1: the corpus holds exactly one real text-native invoice. The scanned specimen has no usable text layer and the adversarial fixtures are this project's own output. The bank-statement half is stronger at thirteen pages across three real statements.

Two of the nine fixtures fail to open under pdfplumber at all. That is expected — they are deliberately adversarial, one empty and one malformed — and is not a finding.

The semantic code index remained truncated throughout, roughly 1027 chunks against roughly 4546 files while reporting itself healthy. Every site here was established by reading the production path and by running the real extractor over real bytes.
