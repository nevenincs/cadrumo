---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S1498-S1499-S1500'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr]]'
---

# `cli-workflow-redesign` `W50.P250.S1498-S1500`

Closed out the remaining W50 census modelo foundation CLI rows.

- Modified: `src/aeat/entrypoints/cli/test_backend_boundary.py`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- Created: `.vault/exec/2026-05-13-cli-workflow-redesign/2026-05-14-cli-workflow-redesign-W50-P250-S1498-S1500-exec.md`

## Description

No new CLI surface or backend implementation was added. The accepted census
modelo foundation paths already route through the shared `app modelo` commands
and existing backend services.

`S1498` was functionally implemented in the CLI: `bindings_list`,
`bindings_preview`, `work_create`, `work_list`, and `work_history` render
through `_emit`. The added `test_census_modelo_results_render_through_emitters`
guard proves those census-facing paths do not bypass the central emitters.

Added two row-specific guards:

- `test_census_modelo_failures_use_central_error_boundary` proves Modelo 037
  active-work refusal emits the registered JSON error through the decorated CLI
  boundary and writes no stdout payload.
- `test_census_modelo_help_uses_accepted_foundation_vocabulary_only` proves
  rendered help for `work create`, `bindings list`, and `bindings preview`
  names the accepted Modelo 036 event periods without advertising rejected
  shims, aliases, placeholders, or live-submission language.

Rows checked in the plan:

- `S1498`
- `S1499`
- `S1500`

## Tests

Focused verification passed:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_modelo.py` passed 56 tests.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_modelo.py`
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_modelo.py`
- `uv run --no-sync aeat app modelo work create --help`
- `uv run --no-sync aeat app modelo bindings list --help`
- `uv run --no-sync aeat app modelo bindings preview --help`
