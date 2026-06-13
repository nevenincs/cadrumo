---
step_id: S323
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P14.S323 — _profiles.py imports from aeat.core (no upward domain→app imports)

## Outcome

`src/aeat/domain/deadlines/_profiles.py` now imports `SetupAnswers` and
`project_answers` from `aeat.core.profile` at module top-level:

```python
from aeat.core.profile import SetupAnswers, project_answers
from aeat.core.profile_catalogue import get_setup_flow
```

The deferred lazy imports of `project_answers` from
`aeat.application.wizard._persistence` and `SetupAnswers` from
`aeat.application.wizard._setup_answers` that previously lived inside the
`taxpayer_profile_from_mapping` function body are fully removed.

The local `SETUP_FLOW = get_setup_flow()` variable inside the function was
renamed to `setup_flow` (snake_case) to satisfy ruff N806.

`src/aeat/application/wizard/_catalogue.py` updated to import `SetupAnswers`
from `aeat.core.profile` so `SETUP_FLOW.answers_model` points to the core
class — making domain `isinstance(typed, SetupAnswers)` checks pass.

`src/aeat/application/wizard/_status.py` updated similarly.

## Files touched

- `src/aeat/domain/deadlines/_profiles.py`
- `src/aeat/application/wizard/_catalogue.py`
- `src/aeat/application/wizard/_status.py`
- `src/aeat/application/wizard/test_setup_runtime.py`
- `src/aeat/application/wizard/test_taxpayer_axes_roundtrip.py`

## Verification

AST-walk test `test_profiles_no_deferred_application_imports` passes.
`test_profiles_imports_setup_answers_from_core` passes. Full wizard + deadlines
suite: 426 pass (1 pre-existing failure in test_engine.py unrelated to these steps).
