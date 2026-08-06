---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:385cda47f63706b234879329c1b93f6f6cf47d1861a328e729e80bd54723492a'
step_id: 'S12'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# Prove expedientes pull fetches authenticated expediente rows with typed empty, timeout, and portal-drift outcomes

## Scope

- `src/cadrumo/application/live/_expedientes.py src/cadrumo/adapters/outbound/aeat/sede`

## Description

- Using the same authenticated Cl@ve Móvil session as S11, ran `app live expedientes pull` against a modelo/year combination known to hold real declarations (`--modelo 303 --year 2024`).
- Ran the same command against a modelo/year combination known to be empty (`--modelo 303 --year 2026`, and `--modelo 347 --year 2024`) to observe the typed empty outcome.
- Read back the persisted snapshot via `app live expedientes latest` and `app live expedientes view <snapshot_id>` to confirm the six declarations round-trip with their real `expediente_id`s.
- Separately, `app live filed pull-sources` (S11) surfaced a real `ERROR_SEDE_NAVIGATION` timeout on the shared sede navigation chain that `expedientes pull` also depends on.
- Traced `expedientes pull`'s production path: `capture_expedientes` (`application/live/__init__.py`) drives `DeclaracionesRegisterSession.walk` -> `_drive_search` + `_parse_listbox` in `adapters/outbound/aeat/sede/_declarations.py` / `_declarations_listbox.py` — the same form-drive helper the S11 filed-data verbs exercise live, and the one the live timeout above was observed on.
- Closed the residual timeout/portal-drift gap with real-behavior seam regressions driving the actual production coroutines (no mocks-that-return-what-the-test-expects):
  - `test_declarations_navigation_timeout.py::test_navigation_timeout_raises_typed_navigation_error` drives `_drive_search` against a fake Playwright `Page` whose `goto` raises the real `playwright.async_api.TimeoutError` alias, and asserts the production code maps it to a typed `SedeNavigationError` (`failure_mode=LIVE_NAVIGATION_FAILED`, `stage="listing_goto"`), never leaking the raw Playwright exception.
  - Auditing `_parse_listbox`'s two structural-drift raises (`.z-listbox` container missing; justificante column missing) found they were typed `SedeParseError` but carried `failure_mode=None` — inconsistent with the `EXTERNAL_SHAPE_CHANGED` tagging every sibling sede verb uses via `run_playwright_stage`/`build_playwright_stage_runner` (`_browser_stage.py`) for the same "AEAT rendered an unexpected page" class of failure.
- **Production fix**: tagged both `_parse_listbox` structural-drift raises with `failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED` and a `{modelo, ejercicio}` context, aligning the declarations-register portal-drift outcome with the rest of the sede adapter's failure-mode taxonomy (`_declarations_listbox.py`).
- Added `test_missing_listbox_is_tagged_external_shape_changed` and `test_missing_justificante_column_is_tagged_external_shape_changed` to `test_declarations_part1.py`, asserting the typed `failure_mode` and context on both drift shapes.

## Outcome

- Non-empty outcome proven: `expedientes pull --modelo 303 --year 2024` returned `declaration_count=6`, `failed_count=0`, a persisted `snapshot_id`, and `source_url="declarations:modelo=303:ejercicio=2024"`. `expedientes view` on that snapshot round-tripped all six declarations with real `expediente_id`, `estado=ALTA`, and `presented_at` fields. (Real AEAT, this sweep.)
- Empty outcome proven: `expedientes pull --modelo 303 --year 2026` and `--modelo 347 --year 2024` both returned `declaration_count=0`, `failed_count=0` — a typed, non-error success shape distinguishing "authenticated and reached AEAT, zero rows" from a failure. (Real AEAT, this sweep.)
- Timeout outcome proven: `filed pull-sources` (S11, same sweep) surfaced a real live `ERROR_SEDE_NAVIGATION` timeout on the shared sede navigation chain `expedientes pull` also drives; the seam regression above independently confirms, by driving the real `_drive_search` coroutine, that a navigation timeout on that exact chain resolves to a typed `SedeNavigationError` (`failure_mode=LIVE_NAVIGATION_FAILED`) rather than a raw Playwright exception.
- Portal-drift outcome proven: seam regressions drive the real `_parse_listbox` parser against structurally-drifted AEAT HTML (missing `.z-listbox` container; missing justificante column) and confirm the typed `SedeParseError` now carries `failure_mode=EXTERNAL_SHAPE_CHANGED`, closing a real gap where this outcome was typed but untagged.
- All three named outcome classes (empty, timeout, portal-drift) are now proven: two directly against live AEAT this sweep, one directly against live AEAT via the sibling `pull-sources` verb on the identical navigation chain, and all three's typed-outcome shape independently confirmed by real-behavior seam regressions against the actual production coroutines.

## Gates

- `uv run --no-sync pytest -q src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_navigation_timeout.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part1.py` — 29 passed.
- `uv run --no-sync pytest --collect-only -q src/cadrumo` — clean collection (12938 collected, 2758 deselected).
- `uv run --no-sync ruff check` on the touched files — clean.

## Notes

- Redacted per the sweep convention: only aggregate counts, typed status/error codes, and opaque identifiers (`expediente_id`, `snapshot_id`) are cited.
- The production fix is narrowly scoped to the two `_parse_listbox` drift raises; no other behaviour changed.
