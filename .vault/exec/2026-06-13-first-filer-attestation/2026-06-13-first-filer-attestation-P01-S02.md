---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S02'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace first-filer-attestation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Add the typed NoPriorObligationProvenance model carrying activity_start_date, provenance kind (operator-declared vs censo-corroborated), and optional censo snapshot id

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add the typed `NoPriorObligationProvenance` pydantic model carrying `facet_kind`, `activity_start_date`, `provenance_kind`, and an optional `censo_snapshot_id`.
- Validate that `provenance_kind` is `OPERATOR_DECLARED` / `CENSO_CORROBORATED`, and that censo-corroborated provenance requires a snapshot id.

## Outcome

- Landed in commit `4026deb0d`. Strict-frozen, exported through `aeat.application.calculations`. The `is_operator_declared` property drives the non-blocking advisory. Validation verified directly (operator-declared default; censo requires snapshot id; facet discriminator rejected as provenance kind).

## Notes

- The model separates the facet-kind discriminator from the provenance kind so the auditable record is unambiguous.
