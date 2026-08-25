---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ddc47bd26cfdc47ff2fe131d186bbe368df6869efc9ea3804ee72936bb196fb9'
step_id: 'S14'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-temporal-coverage with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-08-14-registry-temporal-coverage-plan placeholders are machine-filled by
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
     The Collapse the duplicated filing-eligibility predicate onto the snapshot-owned check and delete the coverage-ledger duplicate and the by-construction-empty filing gap surface outright, replacing them with matrix-derived gaps proven non-vacuous on a synthetic reviewed corpus, with no superseded ledger surface retained beside the matrix and ## Scope

- `src/cadrumo/domain/calculations/registry/_coverage.py`
- `src/cadrumo/domain/calculations/registry/_snapshot.py`
- `src/cadrumo/domain/calculations/registry/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Collapse the duplicated filing-eligibility predicate onto the snapshot-owned check and delete the coverage-ledger duplicate and the by-construction-empty filing gap surface outright, replacing them with matrix-derived gaps proven non-vacuous on a synthetic reviewed corpus, with no superseded ledger surface retained beside the matrix

## Scope

- `src/cadrumo/domain/calculations/registry/_coverage.py`
- `src/cadrumo/domain/calculations/registry/_snapshot.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Route coverage review qualification through `check_snapshot_filing_review_tier`.
- Delete `ModelLawCoverageLedger.filing_gaps` and the superseded coverage-owned review predicate.
- Exercise every derived selection coordinate against a revalidated reviewed synthetic corpus whose layout evidence is absent.

## Outcome

The model-law matrix is the sole projection of required coverage gaps. Coverage retains no legal-review status set, membership predicate, or legal-reference review traversal; snapshot construction is the single owner of that authority boundary.

## Notes

The synthetic corpus preserves official-source guidance while changing only the reviewed filing state and the layout-evidence tier. It validates through a fresh `RegistryValidator` before the matrix audit runs. Temporal-evidence rows and the existing M353 emitted-byte expectation were not changed.
