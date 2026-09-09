---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:51722c96fcb817a1ecd2091aba08f4bcc9b2d725477fa40a29961b4dbe133949'
step_id: 'S364'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Collapse the wizard core registry to its live setup-flow slot, deleting the unused protocol, write-only wizard-flows slot/accessor, and source-code-string subprocess test.

## Scope

- `core wizard catalogue`
- `application registration call`
- `catalogue tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/core/wizard_catalogue.py`
- `M` `src/cadrumo/application/wizard/catalogue.py`
- `M` `src/cadrumo/core/tests/test_wizard_catalogue.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/wizard_catalogue.py src/cadrumo/application/wizard/catalogue.py src/cadrumo/core/tests/test_wizard_catalogue.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/core/tests/test_wizard_catalogue.py src/cadrumo/core/tests/test_wizard_catalogue_errors.py src/cadrumo/application/wizard/tests/test_profile_id_resolution_by_mode.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
