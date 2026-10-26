---
tags:
  - '#exec'
  - '#calendar-obligations'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:a1efcee66d7cb938032cf09aad7e930c20f10a179cc955cc990cf6df9e792498'
related:
  - "[[2026-09-23-calendar-obligations-plan]]"
---

# `calendar-obligations` ledger

## Changes

- `S01` `M` `src/cadrumo/_data/registry/aeat/facts/0143-deadline-calendar-territory-catalogue.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml`
- `S01` `M` `src/cadrumo/domain/calculations/registry/calendar_ccaa_catalogue.py`
- `S01` `A` `src/cadrumo/domain/calculations/registry/tests/test_calendar_ccaa_catalogue.py`
- `S01` `verify:` `ruff check, ruff format, ty, basedpyright, pyrefly on changed files` -> `pass`
- `S02` `M` `src/cadrumo/domain/deadlines/festivos.py`
- `S02` `M` `src/cadrumo/domain/deadlines/models.py`
- `S02` `M` `src/cadrumo/domain/deadlines/profiles.py`
- `S02` `M` `src/cadrumo/domain/deadlines/tests/test_festivos.py`
- `S02` `M` `src/cadrumo/application/overview/calendar.py`
- `S02` `M` `src/cadrumo/application/overview/calendar_models.py`
- `S02` `M` `src/cadrumo/application/overview/tests/test_calendar.py`
- `S02` `M` `src/cadrumo/application/overview/tests/test_home.py`
- `S02` `M` `src/cadrumo/application/overview/tests/test_calendar_filing_evidence.py`
- `S02` `M` `src/cadrumo/application/modelo/tests/test_declarations_calendar.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_overview.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_overview_payloads.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_overview_rendering.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_overview_calendar_verb.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/tests/workbench_fixtures.py`
- `S02` `M` `src/cadrumo/locales/en/application.yml`
- `S02` `M` `src/cadrumo/locales/es/application.yml`
- `S02` `M` `src/cadrumo/locales/ca/application.yml`
- `S02` `M` `src/cadrumo/locales/hu/application.yml`
- `S02` `M` `src/cadrumo/locales/en/cli.yml`
- `S02` `M` `src/cadrumo/locales/es/cli.yml`
- `S02` `M` `src/cadrumo/locales/ca/cli.yml`
- `S02` `M` `src/cadrumo/locales/hu/cli.yml`
- `S02` `A` `src/cadrumo/domain/deadlines/tests/test_holiday_territory_profile.py`
- `S02` `verify:` `ruff, format, ty, basedpyright, pyrefly on changed files` -> `pass`
- `S06` `M` `src/cadrumo/_data/registry/aeat/facts/0066-holiday-calendar-publication.toml`
- `S06` `M` `src/cadrumo/_data/registry/aeat/facts/0067-public-holiday.toml`
- `S06` `A` `src/cadrumo/_data/registry/aeat/legal/dias-inhabiles-age.toml`
- `S06` `A` `src/cadrumo/domain/deadlines/tests/test_holiday_calendar_authority.py`
- `S06` `M` `dev/registry/tests/test_facts_holiday_calendar_retirement.py`
- `S06` `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2023-23637-dias-inhabiles-2024.html`
- `S06` `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2023-23637-dias-inhabiles-2024.html.extracted.json`
- `S06` `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2023-23637-dias-inhabiles-2024.html.extracted.md`
- `S06` `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2024-26935-dias-inhabiles-2025.html`
- `S06` `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2024-26935-dias-inhabiles-2025.html.extracted.json`
- `S06` `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2024-26935-dias-inhabiles-2025.html.extracted.md`
- `S06` `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2025-23702-dias-inhabiles-2026.html`
- `S06` `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2025-23702-dias-inhabiles-2026.html.extracted.json`
- `S06` `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2025-23702-dias-inhabiles-2026.html.extracted.md`
- `S06` `verify:` `pytest -n0 -m unit festivos, holiday authority, retirement master, calendar` -> `pass`
- `S06` `by:` `calendar-holiday-authoring`
- `S03` `M` `src/cadrumo/application/modelo/declarations_calendar.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/declarations/calendar.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/declarations/tests/calendar_fixtures.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py`
- `S03` `M` `src/cadrumo/locales/en/common.yml`
- `S03` `M` `src/cadrumo/locales/es/common.yml`
- `S03` `M` `src/cadrumo/locales/ca/common.yml`
- `S03` `M` `src/cadrumo/locales/hu/common.yml`
- `S03` `verify:` `ruff, format, ty on changed files` -> `pass`
- `S08` `M` `src/cadrumo/application/overview/calendar_warnings.py`
- `S08` `M` `src/cadrumo/domain/deadlines/festivos.py`
- `S08` `M` `src/cadrumo/domain/deadlines/tests/test_festivos.py`
- `S08` `verify:` `ruff, format, ty` -> `pass`
- `S09` `M` `src/cadrumo/core/i18n/locale_catalogue.py`
- `S09` `M` `src/cadrumo/core/i18n/tests/test_locale_catalogue_capture.py`
- `S09` `M` `src/cadrumo/application/modelo/workspace.py`
- `S09` `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `S09` `M` `src/cadrumo/adapters/persistence/profile/tests/test_workspace.py`
- `S09` `verify:` `ruff, format, ty, basedpyright, pyrefly` -> `pass`
- `S07` `M` `src/cadrumo/domain/calculations/registry/authority_store.py`
- `S07` `M` `dev/registry/compiler/authority_database.py`
- `S07` `M` `dev/registry/pipeline/authority_publication.py`
- `S07` `M` `dev/registry/tests/test_authority_artifact_currency.py`
- `S07` `M` `.vault/adr/2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr.md`
- `S07` `verify:` `pytest -n0 -m unit currency, admission, catalogue, festivos (49)` -> `pass`

## Notes

- `S01` published logical_generation 5159b729af5353be4a71983c93a68ad73ad86f39d37578fc70e643257e49e9be
- `S02` S02 also carries the CLI projection and the cli-to-application shift-label key move; the TUI projection is S03
- `S06` published logical_generation 9421767bfd79f05374bb6d99f095071c11d9373d90ef60e4f089e1bedf796880; Val d'Aran and Canarias island days excluded as sub-territorial
- `S03` S06 holiday re-authoring paths were committed inside IVA commit 63a201418e by a shared-index collision; content unchanged
- `S08` profile of the installed first workbench generation: gating fields decoded 441 revisions x3 (15.8s), 61 holiday loads with 5,027 catalogue resolutions (5s); modelo workspace static inspection 11.3s belongs to the modelo workspace owner
- `S09` each casilla label re-read and re-hashed the whole locale shard directory twice (208 labels, about 11 s per workbench generation); assigned to this lane by the coordinator
- `S07` format v2 cutover under coordinator freeze 18:21-18:30; logical_generation 1022f65320ddd012ae398efc420361d2efdb08157ef570d1e0f8e02df7837bb2
