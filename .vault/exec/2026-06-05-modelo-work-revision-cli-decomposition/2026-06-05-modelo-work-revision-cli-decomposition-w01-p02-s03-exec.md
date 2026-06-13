---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S03'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W01.P02.S03 Execution

Extracted `work revisions` and `work revision` into `src/aeat/entrypoints/cli/_modelo_work_revision_cli.py`.

Implementation:
- Added `register_work_revision_commands`.
- Preserved existing Typer signatures, envelope emission, payload shapes, locale activation, selector error handling, and natural-key/raw-ID compatibility.
- Kept business rules delegated to the application layer and shared rendering helpers.
