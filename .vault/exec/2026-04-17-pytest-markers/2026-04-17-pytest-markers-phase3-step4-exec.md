---
tags:
  - "#exec"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-plan]]"
  - "[[2026-04-17-pytest-markers-adr]]"
---

# pytest-markers phase-3 step-4

## migrate-domain-local-state-test-modules

Applied `pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]` to the 30 modules under `src/aeat/adapters/persistence/storage/`, `models/`, `normatives/`, `manuals/`, `corpus/`, `schema/`, `deadlines/`, and `cli/deadlines/`. All `unit`.

## verification

- `uv run pytest src/aeat/storage src/aeat/models src/aeat/normatives src/aeat/manuals src/aeat/corpus src/aeat/schema src/aeat/deadlines src/aeat/entrypoints/cli/deadlines -m unit` -> green.
