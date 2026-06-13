---
step_id: "W04.P22.S426"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-delta8
commit: e7f96f6ec
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# W04.P22.S426 — ApoderadoService disposition audit

Grepped `src/aeat/` for `ApoderadoService` and `ApoderadoConfiguration`.

**Production callers found (5)** in `src/aeat/entrypoints/cli/_config/__init__.py`:
- `apoderado status` command
- `apoderado configure` command
- `apoderado clear` command
- `apoderado check` command
- `apoderado` group import

**Disposition: RETAINED.** Module is properly integrated into the CLI auth
surface. No deletion, no shim. No code changes required.

Additional reference in `src/aeat/core/errors/registry/_domain.py` (error
registry entry for `ApoderadoConfigurationNotSetError`).

**Files touched:** none (audit only)
