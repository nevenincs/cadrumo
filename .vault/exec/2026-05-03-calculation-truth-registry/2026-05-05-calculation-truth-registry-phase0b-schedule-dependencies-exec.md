---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

# `calculation-truth-registry` `Phase 0B` `schedule-dependencies`

Implemented central registry support for profile-based filing schedules and explicit relation period chains.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_schedules.py`
- Modified: `src/aeat/domain/calculations/registry/_snapshot.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/deadlines/_engine.py`
- Modified: `registry/aeat/modelos/111.toml`
- Modified: `registry/aeat/modelos/180.toml`
- Created: `src/aeat/domain/calculations/registry/test_filing_schedule_selection.py`

## Description

The registry schema now accepts `profile_based` modelo cadence, per-revision filing schedules, generic profile predicates, and explicit source and target periods on cross-model relations. Modelo 111 now records both monthly and quarterly official filing schedules from its AEAT instruction corpus. Modelo 180 annual summary relations now state that quarterly Modelo 115 periods feed annual `0A` summary targets.

The schedule selector evaluates nested profile facts through the registry backend without modelo-specific Python branches. Deadline applicability now uses the same predicate evaluation path.

## Tests

Verified registry loading and validation with `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`.

Verified behavior with `uv run pytest src\aeat\domain\calculations\registry\test_filing_schedule_selection.py src\aeat\domain\deadlines\test_engine.py -q`.

Verified focused style and typing with `uv run ruff check` and `uv run ty check` on touched Python surfaces.
