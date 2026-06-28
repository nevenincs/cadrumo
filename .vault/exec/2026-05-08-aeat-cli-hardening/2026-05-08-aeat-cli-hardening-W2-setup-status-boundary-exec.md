---
tags:
  - '#exec'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
  - '[[2026-05-08-aeat-cli-hardening-review-audit]]'
---



# `aeat-cli-hardening` `W2 Boundary Classification` `Setup Status Boundary`

Closed `DISCOVERED-006` for the current setup status behavior.

- Modified: `src/aeat/entrypoints/cli/_setup.py`
- Created: `src/aeat/application/setup_status.py`
- Created: `src/aeat/application/test_setup_status.py`
- Modified: `2026-05-08-aeat-cli-hardening-review.md`
- Created: `2026-05-08-aeat-cli-hardening-W2-setup-status-boundary.md`

## Description

`aeat setup status` no longer computes profile readiness, auth readiness, or the
next command in the CLI handler. The handler now calls `build_setup_status` and
renders the typed `SetupStatusReport`.

The new application service preserves the existing behavior while giving later
UX-006 and UX-009 readiness work a backend owner.

## Tests

Verification commands:

- `uv run --no-sync pytest src/aeat/application/test_setup_status.py src/aeat/entrypoints/cli/test_user_cli_surface.py -k "setup_status or read_only_status or profile_validate"`
- `uv run --no-sync ruff check src/aeat/application/setup_status.py src/aeat/application/test_setup_status.py src/aeat/entrypoints/cli/_setup.py`
- `uv run --no-sync ruff format --check src/aeat/application/setup_status.py src/aeat/application/test_setup_status.py src/aeat/entrypoints/cli/_setup.py`
- `uv run --no-sync ty check src/aeat/application/setup_status.py src/aeat/entrypoints/cli/_setup.py`

The first ruff and ty pass failed because `profile validate` still used
`validate_profile` after the status refactor. The existing import was restored,
then the focused tests and checks passed.
