---
step_id: "W04.P22.S422"
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

# W04.P22.S422 — get_logger swap at core/profile_catalogue.py

Replaced `import logging` + `_log = logging.getLogger(__name__)` with
`from .logging import get_logger` + `_log = get_logger(__name__)`.

No circular-import risk: `core.logging` has no dependency on
`core.profile_catalogue`. Import resolves cleanly at runtime.

**Files touched:** `src/aeat/core/profile_catalogue.py`
