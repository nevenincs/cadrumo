---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:7eb19affac24b7499a7543d7a8e7aa6379a62f5f49fd6e2321481d79783e987b'
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
