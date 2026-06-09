---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
step_id: 'S01'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace justfile-redesign with a kebab-case feature tag, e.g. #foo-bar.
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

# extract complexity calculation heredocs with zero-noise success filtering

## Scope

- `scripts/audit_complexity.py`

## Description

- Extracted complexity calculation logic from the `justfile` into a standalone, robust Python script `scripts/audit_complexity.py`.
- Configured the script to execute `radon cc`, `radon mi`, and `complexipy` with custom thresholds.
- Enforced a zero-noise output policy by filtering out success messages and only showing actionable grade violations (CC >= C, MI < A, Cognitive Complexity > 20).
- Handled cases where `complexipy` is missing or fails to parse files gracefully.

## Outcome

The script `scripts/audit_complexity.py` was created and successfully executed via `uv run --no-sync python scripts/audit_complexity.py`. It correctly filtered out passing files and listed the exact functions/files exceeding complexity thresholds.

## Notes

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
