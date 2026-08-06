---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:bec8157b0b6d3175130d516fbd4f9bc12ea98dc56da958adac76b5938f585e68'
step_id: 'S35'
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
     The S35 and 2026-08-06-invoice-canonical-structure-plan placeholders are machine-filled by
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
     The Close the bucket-attribution asymmetry before the fold, making a persisted canonical Invoice carry a bucket_id by requiring it at the construction boundary rather than defaulting to None, and correcting the InvoiceCatalogueRepository ownership-guard docstring which today asserts as its stated justification that most invoices carry no bucket at all, a premise the production writers refute because every canonical construction path passes a resolved bucket_id and ## Scope

- `src/cadrumo/domain/invoices/_models.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Close the bucket-attribution asymmetry before the fold, making a persisted canonical Invoice carry a bucket_id by requiring it at the construction boundary rather than defaulting to None, and correcting the InvoiceCatalogueRepository ownership-guard docstring which today asserts as its stated justification that most invoices carry no bucket at all, a premise the production writers refute because every canonical construction path passes a resolved bucket_id

## Scope

- `src/cadrumo/domain/invoices/_models.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Traced how the resolver binds its repository before choosing a remedy, which changed what the correct remedy was.
- Narrowed the attribution filter so only a POPULATED, mismatching bucket excludes, aligning the projection with the rule the persistence guard already applied.
- Corrected the persistence guard's docstring, which justified its tolerance with a claim the writers refute.
- Added the declaration proof and a cross-bucket isolation positive control.
- Widened the test helper's bucket parameter so an unattributed invoice is constructible in a test at all, which it previously was not.

## Outcome

**The remedy changed once the mechanism was traced, and the change matters.**

The Step as written proposed requiring a bucket at the construction boundary. Measuring first showed the comparison itself was **wrong**, not merely permissive. The resolver opens the repository against the context bucket, and that repository refuses a foreign row on read, so every invoice reaching the filter came from THIS bucket's encrypted store. An unattributed invoice therefore belongs to this bucket — it simply never had the redundant field stamped. Excluding it was a defect in the filter, not a missing constraint on the writer.

So the filter now excludes only a populated, mismatching bucket, which is exactly the rule the persistence guard already applied. Before this the two layers held **contradictory beliefs about the same record**: the store treated an unattributed invoice as belonging, and the projection treated it as foreign. A disagreement between the store and the projection about whether a record exists is resolved in favour of declaring, because the alternative is an invisible omission from a filing.

Requiring the field at construction instead would have left the wrong comparison in place and merely made it harder to reach — the defect would have survived, waiting for the first writer that omitted a bucket.

**Severity, stated precisely: latent, not live.** No production path persists an unattributed invoice. The construction primitive types the bucket as a required string and all four of its production callers resolve one first. The fold is what makes it live, by widening the producer set onto a model whose default is unset, and nothing downstream would have caught the first producer that omitted one.

**The docstring correction is the more dangerous half.** The guard justified permitting an unattributed invoice by asserting that most invoices carry no bucket at all. That is false, and it was not a stray comment: it was the stated PERMISSION a future writer would have reasoned from when deciding whether leaving the bucket unset was acceptable. This is the same defect class as the M349 guard whose justification the tree refutes, now found in a second location.

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
    23 passed in 24.22s

Regression scope covering the projection, the aggregate and the persistence adapter together:

    uv run --no-sync pytest src/cadrumo/application/invoices src/cadrumo/domain/invoices src/cadrumo/adapters/persistence/profile -q --no-header
    510 passed in 39.35s

    uv run --no-sync ruff check <the three changed files>
    All checks passed!

The proof is a pair, and the second half is what keeps the first honest: an unattributed invoice in the bucket's store is declared, AND an invoice naming a different bucket is still excluded. Without the control the narrowing would read as correct while having disabled cross-bucket isolation — a confidentiality failure rather than a declaration one, since one taxpayer's invoice would surface in another's return.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The test helper could not previously construct an unattributed invoice: its bucket parameter was typed as a required string, so the case the filter mishandled was unreachable from the test surface. A gap that cannot be expressed in a fixture cannot be caught by one, which is part of why this survived.

The field-requirement half of the Step as originally written is deliberately NOT implemented. Tightening the canonical aggregate to demand a bucket would break the roundtrip fixtures that legitimately construct an unattributed invoice, and would buy nothing now that the filter is correct. If a later Step wants the writers constrained as well, that is a separate decision with its own blast radius, not a silent rider on this fix.
