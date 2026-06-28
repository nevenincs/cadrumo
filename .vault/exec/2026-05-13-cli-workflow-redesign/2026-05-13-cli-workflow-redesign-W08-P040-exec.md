---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W08.P040'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr]]'
---

# `cli-workflow-redesign` `W08.P040`

Completed thin CLI exposure verification for profile bucket behavior.

- Modified: `src/aeat/entrypoints/cli/_config.py`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `src/aeat/entrypoints/cli/filing/test_filing_cli.py`
- Modified: `src/aeat/entrypoints/cli/test_backend_boundary.py`

## Description

The retained config profile commands continue to delegate to profile, wizard,
workflow, and storage services. The CLI renders through `_emit`, reports
validation through the central command boundary, and exposes no profile path or
JSON draft input surface. Filing build from a JSON input file is absent.

Closed plan rows: `W08.P040.S0235`, `W08.P040.S0236`,
`W08.P040.S0237`, `W08.P040.S0238`, `W08.P040.S0239`,
`W08.P040.S0240`.

## Tests

`uv run --no-sync pytest src/aeat/application/test_config_parity.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/test_backend_boundary.py -q`
