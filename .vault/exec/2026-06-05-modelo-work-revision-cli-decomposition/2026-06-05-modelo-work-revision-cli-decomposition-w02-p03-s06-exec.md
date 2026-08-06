---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:a23ab4c3bf36497e03ca34bf517a3e5846f00687da59012949597a34bba74236'
step_id: 'S06'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W02.P03.S06 Execution

Extracted `work verify` and `work file` into `src/aeat/entrypoints/cli/_modelo_work_verification_cli.py`.

Implementation:
- Added `register_work_verification_commands`.
- Split command installation through private helpers so the public registrar stays small.
- Preserved existing Typer signatures, output language activation, active-profile guard, envelope output, id-type hint handling, and workflow gate propagation.
- Kept revision state transitions inside application actions: `verify_modelo_revision` and `file_modelo_revision`.
