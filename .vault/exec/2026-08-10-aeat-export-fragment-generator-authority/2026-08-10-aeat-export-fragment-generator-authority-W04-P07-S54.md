---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a68bb2b1a01c2b02af670c819e2571fad435a974c795161f866a7d058f8c8616'
step_id: 'S54'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-export-fragment-generator-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S54 and 2026-08-10-aeat-export-fragment-generator-authority-plan placeholders are machine-filled by
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
     The Ground and implement the canonical M303 differentiated-sector source taxonomy before projection by researching and approving the source authorities for current-versus-investment, REAGP, rectification, and bienes-inversion regularisation, preserving the chosen closed classification into frozen IVA observations, defining transaction and asset linkage, adjustment ownership, migration and backfill boundaries, and fail-closed behavior, then landing the canonical observation and resolver changes with real ledger, asset, and refusal proofs and no scalar, mapping, label, or slot inference and ## Scope

- `src/cadrumo/domain/iva/`
- `src/cadrumo/application/aggregation/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/domain/bienes_inversion/`
- `.vault/research/`
- `.vault/adr/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Ground and implement the canonical M303 differentiated-sector source taxonomy before projection by researching and approving the source authorities for current-versus-investment, REAGP, rectification, and bienes-inversion regularisation, preserving the chosen closed classification into frozen IVA observations, defining transaction and asset linkage, adjustment ownership, migration and backfill boundaries, and fail-closed behavior, then landing the canonical observation and resolver changes with real ledger, asset, and refusal proofs and no scalar, mapping, label, or slot inference

## Scope

- `src/cadrumo/domain/iva/`
- `src/cadrumo/application/aggregation/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/domain/bienes_inversion/`
- `.vault/research/`
- `.vault/adr/`

## Description

- Replace the retired IVA input-kind vocabulary with the closed deduction-fact taxonomy and immutable typed provenance.
- Preserve exact classification through transaction persistence, candidate freezing, registry selection, and aggregation.
- Enforce reciprocal transaction-to-investment-asset identity, profile, year, and sector ownership in the Bienes register.
- Cut transaction, index, and Bienes secure payloads over through one explicit cross-namespace CAS migration.
- Refuse missing authority, ambiguous backfill, old-schema ordinary reads, reused rectifications, and illegal REAGP or rectification combinations.
- Prove strict behavior with real encrypted repositories and evidence-bearing domain fixtures.

## Outcome

The new-only taxonomy is the sole executable IVA deduction authority. Cross-namespace migration validates the complete persisted set before one atomic replacement, production aggregation requires the persisted Bienes authority, and no legacy enum, default backfill, dual read, or unguarded aggregation route remains.

Independent review passed with zero critical, high, medium, or low findings. The affected aggregation lane passed 174 tests, the focused S54 lane passed 76 tests, and the corpus and manipulation lane passed 15 tests. Ruff passed and Basedpyright reported zero errors, warnings, or notes.

## Notes

Initial review found incomplete production reciprocity and namespace-local migration. A second review found retained default backfill and a public low-level aggregation bypass. Each finding was remediated and re-reviewed before closure. Evidence-less corpus fixtures now assert strict missing-classification refusal instead of receiving inferred test classifications.
