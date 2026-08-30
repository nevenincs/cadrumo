---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:386386b6413bc01e0408c2b687777e39682ca735d552de9c97767801b5ee85a7'
step_id: 'S75'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Add the dedicated installed TUI console entry point targeting the launcher directly

## Scope

- `pyproject.toml`

## Changes

- `verify:` `importlib.metadata.entry_points(group="console_scripts")` -> `pass (aeat -> cadrumo.entrypoints._cli_main:main; aeat-tui -> cadrumo.entrypoints.tui.launcher:main, both resolving to callables)`

## Notes

No file changed. The entry point this row asks for was already present in
`[project.scripts]` and had no execution record; it landed incidentally in
commit fb74ced033 (`relocation:deadlines,google,sede`) rather than under this
row. Closed on verification rather than on a diff: `aeat-tui` is declared,
installed, and resolves to `launcher.main`, and `entrypoints/tui/__main__.py`
exists for the module form.

Recorded because the row was indistinguishable from unstarted work when read
from the plan alone -- the deliverable existed while the row stayed open, which
is the same unmarked-but-done shape found on W05.P23.S322 in this session.
