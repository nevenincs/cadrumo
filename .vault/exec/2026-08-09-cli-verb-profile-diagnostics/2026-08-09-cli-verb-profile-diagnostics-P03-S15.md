---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:7bfa93e5cdc0573eefa0ab6ca7b4cb60da776c0ffb5844e5eb68e4c035eb69eb'
step_id: 'S15'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add real CLI tests asserting app modelo requires names the missing profile field by label rather than by binding id

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_modelo_requires_profile_grounding.py`

## Description

- Added an anchor test asserting the committed registry actually declares profile bindings that name profile keys, so the assertions below cannot pass over an empty set.
- Added a whole-registry test rendering every such binding's keys through the shared enrichment helper and asserting no rendered string contains the binding id.
- Moved the checklist mapping tests into the application package, where the function they exercise lives.

## Outcome

The rendering is asserted over every committed profile binding rather than one hand-picked example, so an unlabelled field anywhere in the registry fails this rather than only the case a fixture happened to choose.

The test split is the substantive correction. The first draft asserted the checklist mapping from the entrypoints test package by importing a private application module, which is exactly the cross-package private import this project's boundaries forbid. Rather than exempt it, the tests were moved to the package that owns the function. The import-hygiene gate would have caught this, but it was moved because the boundary is right, not because a gate objected.

## Verification

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_data_inventory_profile_keys.py src/cadrumo/entrypoints/cli/tests/test_modelo_requires_profile_grounding.py -n 0 -q
    5 passed in 10.98s

    uv run --no-sync pytest src/cadrumo/tests/test_import_hygiene_gate.py src/cadrumo/tests/test_marker_integrity.py -n 0 -q
    51 passed in 148.82s (0:02:28)

## Notes

An earlier draft carried a test asserting the checklist reports no profile keys when there is no active profile. It was removed rather than kept: it asserted an empty tuple on a branch that cannot populate one, so it could not have failed against a broken mapping.
