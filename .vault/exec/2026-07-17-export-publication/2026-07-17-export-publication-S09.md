---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S09'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Regenerate the operator reference pages for portable export and subject access from the frozen live surface

## Scope

- `docs/reference/import-export-and-evidence.md`

## Description

- Add portable-profile-export and subject-access-request rows to the export reference table in `docs/reference/import-export-and-evidence.md`, each naming what it produces and what it does not prove.
- Add a paragraph, grounded in the live command surface, describing the two purposes as one export service and one bundle schema, the derived data categories, the atomic staged-then-replaced publication, and the equal cleartext handoff risk both purposes carry.

## Outcome

The reference now covers the portable profile export and the subject-access request faithfully to the frozen live CLI surface. The documented-command inline-span gate passes and the nitpicky docs build passes.

## Notes

Command references are cited by bare command path (no option/arg tokens inline) to satisfy the user-doc inline-aeat-span baseline; options are described in prose. The reference doc is hand-authored under the documentation workflow, not a generator-managed file, so the change is an authored edit rather than a regenerated managed zone.
