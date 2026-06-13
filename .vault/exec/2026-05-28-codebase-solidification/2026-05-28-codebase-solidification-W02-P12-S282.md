---
step_id: S282
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W02.P12.S282-S291 — A3 sede navigation + portal locale cluster

## Scope

Ten Steps closed in one execution session: S282-S288 thread `translated_message=` on
`SedeNavigationError` / `SedeParseError` raises across `_declarations.py` and
`_censo_live.py`; S289 adds a real-behavior test file; S290 threads `translated_message=`
on `PortalNotFoundError`; S291 adds real-behavior tests for the portal error.

## Outcome

### S282 — session_expired_nav_failed
`_declarations.py` final-URL check raise (post-goto to `_LISTING_URL`): added
`translated_message=tr("adapters.sede.errors.session_expired_nav_failed")`.

### S283 — form_render_timeout
`_declarations.py` Modelo-label wait raise: added
`translated_message=tr("adapters.sede.errors.form_render_timeout")`.

### S284 — cotejo_nav_failed
Three `SedeNavigationError` raises in `fetch_cotejo_justificante_ref` (Ver-button click,
cotejo-page settle, cotejo-URL prefix check): all carry
`translated_message=tr("adapters.sede.errors.cotejo_nav_failed")`.

### S285 — ejercicio_unavailable
Two `SedeNavigationError` raises (`capture_filed_declaration_observation` at line ~272
and `fetch_cotejo_justificante_ref` at line ~820): both carry
`translated_message=tr("adapters.sede.errors.ejercicio_unavailable")`.

### S286 — listbox_missing / justificante_column_missing / parse_failed
Three `SedeParseError` raises in `_parse_listbox`: HTML-parse failure gets
`parse_failed`, missing `.z-listbox` gets `listbox_missing`, missing justificante column
gets `justificante_column_missing`.

### S287 — listing_nav_failed
`_declarations.py` goto `_LISTING_URL` `PlaywrightError` catch: added
`translated_message=tr("adapters.sede.errors.listing_nav_failed")`.

### S288 — no_auth_session in _censo_live.py
Added `from .....core.i18n import tr` import. `SedeNavigationError` raise at line 80
(missing `storage_state_path`) now carries
`translated_message=tr("adapters.sede.errors.no_auth_session")`.

### S289 — test_declarations_locale.py
New file `src/aeat/adapters/outbound/aeat/sede/test_declarations_locale.py` with:
- `TestParseListboxTranslation`: drives `_parse_listbox` with broken HTML to assert
  `SedeParseError.translated_message` equals the expected locale string.
- `TestSedeNavigationErrorTranslationContract`: constructor round-trips.
- `TestSedeParseErrorTranslationContract`: constructor round-trips.
All 8 tests pass.

### S290 — PortalNotFoundError translated_message
Added `from ...core.i18n import tr` to `application/portals/_service.py`. The
`PortalNotFoundError` raise at line 97 now carries
`translated_message=tr("application.portals.errors.portal_not_found")`.

### S291 — TestPortalNotFoundErrorLocale
`TestPortalNotFoundErrorLocale` class added to `test_service.py` with three tests:
real raise via empty registry, key resolves to non-placeholder, message != key path.
All pass.

## Locale keys

Scaffold + set for en/es/ca/hu (9 keys):
- `adapters.sede.errors.session_expired_nav_failed`
- `adapters.sede.errors.form_render_timeout`
- `adapters.sede.errors.cotejo_nav_failed`
- `adapters.sede.errors.ejercicio_unavailable`
- `adapters.sede.errors.listbox_missing`
- `adapters.sede.errors.justificante_column_missing`
- `adapters.sede.errors.listing_nav_failed`
- `adapters.sede.errors.parse_failed`
- `application.portals.errors.portal_not_found`

`python -m aeat.locales scaffold --check` returns `ok` for all four locales.

## Files touched

- `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`
- `src/aeat/application/portals/_service.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`
- `src/aeat/adapters/outbound/aeat/sede/test_declarations_locale.py` (new)
- `src/aeat/application/portals/test_service.py`

## Test outcome

`pytest test_declarations_locale.py test_service.py` — 23 passed, 0 failed.

## Collision signal

`git diff` of target paths before edits: no output (clean). Locale files had pre-existing
sede placeholder keys from earlier campaign step — swept forward (set real values), never
reverted.

## Commit SHA

22904f4b5
