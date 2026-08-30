---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:b6ba05acac5b107d6290c7eefe98aaddf6e01d1bb860b6fc8b946fda346a89e5'
step_id: 'S52'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Render the workspace overview destination with natural and exact address disclosure, the REVISION COORDINATES, status, capability summary, refusals, safe actions, and collapsible narrow-terminal chrome. NARROWED: 'revision timeline' means the coordinates, not a chronology -- law_selected_revision_id plus the requested-versus-stored POINT assertions and review_status. Workspace V1 exposes no sequence-over-time anywhere, so a view rendering a chronology would author a temporal claim the application layer never made, which is the same violation class as synthesising provenance edges. EXCLUDED FROM THIS ROW: an actual revision history over time remains unrepresented. If operators need one it is an application-layer producer, not a view, and it needs its own row rather than being smuggled into this one

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view/overview.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/view/overview.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_overview.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/ -m "unit or integration" -n0 -q` -> `pass` (112 passed; the 2 failures are in `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`, peer-held and outside this Step)
