---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
step_id: 'S53'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# W03.P09.S53 workflow surface redaction expectations

Scope: update workflow-surface tests so profile and bucket routing identifiers assert through the centralized CLI redaction vocabulary.

## Description

- Replace hard-coded profile and bucket placeholders with shared redaction constants.
- Assert the raw UUID profile bucket id does not appear in the parsed profile-status payload where the test has that id available.
- Preserve operator-facing profile labels and domain identifiers that remain intentionally visible.

## Outcome

S53 is implemented for the current `test_workflow_surface.py` surface.

## Notes

Focused ruff and pytest passed for `test_workflow_surface.py`. No mocks, skips, xfails, or suppressions were introduced.
