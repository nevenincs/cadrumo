---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P02.S09'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P02.S09`

Closed WCLI-4 for `_app_live.py`: the portal `view` command no longer
routes typed portal lookup errors through a broad `Exception` catch or
raw `str(exc)` rendering.

- Modified: `src/aeat/entrypoints/cli/_app_live.py`
- Modified: `src/aeat/entrypoints/cli/test_live_portals_verbs.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Imported `resolve_error_message` into the live CLI surface and narrowed
the portal `view` boundary to `UnknownPortalError`, the public typed
exception raised by `domain.portals.get_portal` for unknown portal ids.
The command now constructs `typer.BadParameter` from the registered
error renderer instead of from `str(exc)`.

Tightened the unknown-portal CLI regression test to assert a clean
operator-facing refusal with no traceback and with the message resolved
from the registered `UnknownPortalError`.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_live_portals_verbs.py` passed.

`uv run pytest -q src/aeat/entrypoints/cli/test_live_portals_verbs.py` passed with 9 tests in 1.80s.

`rg -n "BadParameter\\(str\\(exc\\)\\)" src/aeat/entrypoints/cli/_app_live.py` found no remaining raw `str(exc)` conversions in `_app_live.py`.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S09` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P02-S09.md src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_live_portals_verbs.py` passed with the existing plan-file CRLF normalization warning.
