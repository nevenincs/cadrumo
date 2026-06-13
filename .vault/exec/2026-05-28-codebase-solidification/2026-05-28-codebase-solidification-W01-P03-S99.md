---
step_id: S99
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S99 — SedeNavigationError no_auth_session threading

## Outcome

Threaded `translated_message=tr("adapters.sede.errors.no_auth_session")` on every
`SedeNavigationError` raise across five Sede modules:

- `_auth_state.py`: two raises (storage_state_path is None; persisted is None)
- `_walker.py`: one raise (_open_browser_page guard)
- `_declarations.py`: one raise (_open_register_page guard)
- `_notifications.py`: one raise (_fetch_and_parse guard)
- `_iva_compensation_wallet.py`: one raise (fetch_iva_compensation_wallet guard)

Added `from .....core.i18n import tr` import to all five modules.

Scaffolded `adapters.sede.errors.no_auth_session` via `python -m aeat.locales scaffold`
then set values in all four catalogues (es, en, ca, hu).

## Files touched

- `src/aeat/adapters/outbound/aeat/sede/_auth_state.py`
- `src/aeat/adapters/outbound/aeat/sede/_walker.py`
- `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- `src/aeat/adapters/outbound/aeat/sede/_notifications.py`
- `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

`python -m aeat.locales audit` clean on all four catalogues.
