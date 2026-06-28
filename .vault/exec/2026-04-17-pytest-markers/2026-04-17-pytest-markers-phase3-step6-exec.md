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

# pytest-markers phase-3 step-6

## migrate-domain-infra-test-modules

Applied module-level `pytestmark` per inventory across the 33 modules spanning `cli/`, `setup/`, and top-level `tests/*.py`. Four modules received `live_read`: `cli/_test_cloud_live.py`, `cli/_test_docs_live.py`, `cli/_test_drive_live.py`, `cli/_test_sheets_live.py`. `tests/live/test_google_fixtures_smoke.py` received `[live_read, domain_infra, skipif(...)]` preserving the dual-opt-in skipif guard.

## verification

- `uv run pytest src/aeat/_test_auth.py src/aeat/_test_env_io.py src/aeat/cli src/aeat/setup tests/test_config.py tests/test_docs.py tests/test_release_config.py -m unit` -> green.
- `uv run pytest tests/test_marker_integrity.py` -> 148 passed (covers google fixtures module with skipif preserved).
