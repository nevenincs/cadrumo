---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:5cc4f156cc946b42e137723aeef4e90e1e221374f91211b7e544243109cc17d1'
step_id: 'S364'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
