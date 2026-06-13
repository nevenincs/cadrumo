---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---

# Modelo 131 Behaviour Gate Step

## Scope

- Exercise the current Modelo 131 registry through the real calculation runtime.
- Exercise Modelo 131 deadline applicability through the registry-backed
  deadline engine.
- Keep export and historical revision rows open until the official
  activity-detail record structures and older record designs are represented.

## Changes

- Added a committed-registry calculation test for current Modelo 131 objective
  estimation totals.
- Added deadline-engine coverage proving Modelo 131 obligations are emitted
  only for profiles that use IRPF estimacion objetiva.
- Updated the plan ledger with checked current-2026 subrows and explicit open
  rows for historical revisions, live fixtures, and activity-detail export
  layout support.

## Verification

- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py src\aeat\application\setup\test_env_writer.py src\aeat\application\setup\test_models.py -q`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
- `uv run ruff check registry\aeat\modelos\131.toml src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py src\aeat\domain\deadlines\_models.py src\aeat\application\setup\_models.py src\aeat\application\setup\_env_writer.py src\aeat\domain\calculations\registry\_schema.py`
- `uv run ty check src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py src\aeat\domain\deadlines\_models.py src\aeat\application\setup\_models.py src\aeat\application\setup\_env_writer.py src\aeat\domain\calculations\registry\_schema.py`
- `rg -n "legacy|migration|transient|hard cut|previous state|past state|stub|shim|disabled" registry\aeat\modelos\131.toml src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py src\aeat\domain\deadlines\_models.py src\aeat\application\setup\_models.py src\aeat\application\setup\_env_writer.py src\aeat\domain\calculations\registry\_schema.py`
- `git diff --check -- registry\aeat\modelos\131.toml src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\deadlines\test_engine.py src\aeat\domain\deadlines\_models.py src\aeat\application\setup\_models.py src\aeat\application\setup\_env_writer.py src\aeat\domain\calculations\registry\_schema.py registry\aeat\legal\irpf.toml`
