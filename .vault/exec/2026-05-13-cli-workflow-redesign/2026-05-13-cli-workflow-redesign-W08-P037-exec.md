---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W08.P037'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr]]'
---

# `cli-workflow-redesign` `W08.P037`

Completed the shadow duplicate removal phase for profile value persistence.

- Deleted: `src/aeat/adapters/persistence/profile/tax_residence.py`
- Deleted: `src/aeat/adapters/persistence/profile/test_tax_residence.py`
- Deleted: `src/aeat/application/profile/_storage_namespaces.py`
- Modified: `src/aeat/core/config.py`
- Modified: `env/.env.example`
- Modified: `src/aeat/application/workflow/_adapters.py`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_backend_boundary.py`

## Description

Removed profile JSON/path settings, profile-path persistence adapters, and JSON
draft input provider wiring. The filing CLI no longer exposes `build --inputs`;
retained filing commands operate on drafts already persisted through the secure
repository. Boundary inventory was updated so deleted filing-build symbols are
not treated as a live CLI/backend gap.

Closed plan rows: `W08.P037.S0217`, `W08.P037.S0218`,
`W08.P037.S0219`, `W08.P037.S0220`, `W08.P037.S0221`,
`W08.P037.S0222`.

## Tests

`uv run --no-sync pytest src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/tests/test_config.py -q`
