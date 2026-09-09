---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:bdce1d26506ed1b2c85dfe21f8030b636aec1baedc1a69cc5d17c760769d62bf'
step_id: 'S352'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unrouted profile status projection and Textual screen with their dev-only fixtures, private-helper tests, visual megasuite, and public-module inventory.

## Scope

- `profile status projection and TUI`
- `status tests`
- `dev surface registry`
- `retained theme behavior`
- `exact reachability`

## Changes

- `D` `src/cadrumo/application/user_profile/status_projection.py`
- `D` `src/cadrumo/application/user_profile/tests/test_status_projection.py`
- `D` `src/cadrumo/application/user_profile/tests/test_status_indexed_fact_masking.py`
- `D` `src/cadrumo/application/user_profile/tests/test_public_definition_identity.py`
- `D` `src/cadrumo/entrypoints/tui/profile/status.py`
- `D` `src/cadrumo/entrypoints/tui/tests/test_status_screen.py`
- `D` `src/cadrumo/entrypoints/tui/tests/test_status_notices_wiring.py`
- `D` `src/cadrumo/entrypoints/tui/tests/test_status_session_deadlines.py`
- `D` `src/cadrumo/entrypoints/tui/tests/test_visual_verification.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_theme.py`
- `M` `dev/tui/harness/surfaces.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_theme.py -q` -> `pass (33 passed)`
- `verify:` `uv run --no-sync ruff check dev/tui/harness/surfaces.py src/cadrumo/entrypoints/tui/tests/test_theme.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (22 unreachable modules; down from 24)`

## Notes

The broad profile/config run reached 529 passes but remained red on peer-owned custody composition, storage refusal exception shape, lock propagation, cleared-path inventory, and a removed Google handler. Those failures do not touch this status deletion; the two campaign-owned import errors it exposed were removed with their metastate tests.
