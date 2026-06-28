---
tags:
  - "#exec"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-self-healing-sync-plan]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
---

# step 9 — verification

Full verification pass on Windows:

- `just lint` — ruff: all checks passed.
- `just typecheck` — ty: all checks passed.
- `just test` — pytest: 173 passed, 1 skipped (pre-existing
  unix-default platform skip in `cli/_test_doctor.py`, unrelated),
  8 deselected (live marker).
- `just hooks` — prek: all hooks passed (trim/eof/yaml/toml/large/
  merge/private-key/ruff/ruff-format/ty).
