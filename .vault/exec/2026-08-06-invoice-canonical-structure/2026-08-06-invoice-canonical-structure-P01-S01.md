---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:794081621bee4e3e1a65e240ea8b118d3406697d865625bec69257fb42591cc7'
step_id: 'S01'
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
     The S01 and 2026-08-06-invoice-canonical-structure-plan placeholders are machine-filled by
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
     The Prove declarable coverage, that every declarable fact the slim store contributes today is reachable on the canonical path for both M347 per-party totals and M349 operator rows, asserting fact-level reachability and never output-equality with the double-counting two-store union and ## Scope

- `src/cadrumo/application/invoices/tests/test_source_resolver.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove declarable coverage, that every declarable fact the slim store contributes today is reachable on the canonical path for both M347 per-party totals and M349 operator rows, asserting fact-level reachability and never output-equality with the double-counting two-store union

## Scope

- `src/cadrumo/application/invoices/tests/test_source_resolver.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Ran semantic discovery for the invoice-to-declarable-fact projection, then confirmed the exact declaration sites with a targeted search at `HEAD`.
- Derived the declarable-fact contract from `InvoiceObservation` rather than by hand, excluding the identity and rectification axes by name.
- Added an enumeration guard pinning that contract against the observation model's own field set, so a fact dropped from the contract fails loudly instead of shrinking the coverage the other proofs assert.
- Added M349 and M347 fact-reachability proofs, each projecting the slim record and its canonical twin ALONE and comparing the resulting fact dicts.
- Added a refusal proof for the tax-id/country mismatch the slim model permits and the canonical model rejects, matched on the message rather than the exception type.
- Corrected a Yoda-condition lint finding by hand rather than through a broad autofix run, which can disturb unrelated suppressions in this shared tree.

## Outcome

**The predicted RED did not occur, and the Step closes GREEN on a complete measurement rather than on a gap.** All seven declarable facts the slim store contributes are reachable on the canonical path, for both the M347 per-party totals and the M349 operator rows. Declarable coverage is proven complete, which is what `P03` required from this Step.

The proof is structured as the plan specified: each store is projected alone against one explicit contract, never compared against a resolver wired to both. That union double-counts an invoice held in both stores, so a union-equality assertion would demand the canonical path reproduce the double-count, and would be either unsatisfiable or a pin on the defect the campaign removes.

The reason the criterion was green is load-bearing and re-scopes the next Step. The canonical aggregate lacks the slim path's EU-VAT-ID preference and country-prefix derivation, and needs neither: a non-`ES` counterparty country forces the counterparty tax id to be that country's published NIF-IVA, so the EU VAT number is already the only representable party identity. The country is a required first-class field rather than a value derived from a prefix, and the Greek ISO/VAT split is handled by the same central identity authority.

One construction in the first draft of this proof was refused by the canonical model, which is how the mechanism was found: a Spanish-format NIF against a German country is representable as slim and is rejected as canonical.

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_source_resolver.py -p no:randomly -q --no-header
    21 passed in 22.02s

Seventeen pre-existing tests in that module plus the four added here, so the addition is proven not to have regressed the surrounding resolver coverage.

The intermediate RED is part of the evidence and is quoted rather than summarised, because it is what located the conserving mechanism:

    pydantic_core._pydantic_core.ValidationError: 1 validation error for Invoice
    Value error, IVA number 'ESB12345678' is not a valid Germany NIF-IVA: expected DE + 9 digits (e.g. DE123456789)

Lint:

    uv run --no-sync ruff check src/cadrumo/application/invoices/tests/test_source_resolver.py
    All checks passed!

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
