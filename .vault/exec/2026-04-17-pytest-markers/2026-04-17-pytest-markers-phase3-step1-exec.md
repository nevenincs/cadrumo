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

# pytest-markers phase-3 step-1

## migrate-domain-aeat-remote-test-modules

Applied `pytestmark = [pytest.mark.<access>, pytest.mark.domain_aeat_remote]` to every file in the inventory (36 modules) via the `_migrate_markers.py` helper script (deleted after use). Per-function `@pytest.mark.unit` / `@pytest.mark.live` decorators were stripped; `@pytest.mark.parametrize` and `@pytest.mark.skipif` were preserved.

## verification

- Integrity test covers every file: `uv run pytest tests/test_marker_integrity.py -k domain_aeat_remote` -> all pass.
- `uv run pytest src/aeat/auth src/aeat/browser src/aeat/inbox src/aeat/justificante src/aeat/status src/aeat/casillas src/aeat/sync src/aeat/portals -m unit` -> green.
