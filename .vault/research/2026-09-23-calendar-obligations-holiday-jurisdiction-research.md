---
tags:
  - '#research'
  - '#calendar-obligations'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:29542a3e43bced22bea3a0e8aac0cf4832ca055eea522d97d4aa7961eb84bb98'
related: []
---

# `calendar-obligations` research: `Deadline holiday jurisdiction grounding`

Which holidays extend an AEAT filing deadline, and whose territory decides it. The overview calendar shifted every deadline national-only. The official sources show that autonomic and municipal holidays extend deadlines as well, keyed to the taxpayer's residence or the seat of the administrative body. Modelo 369 is the one exception. Measured 2026-09-23.

## Findings

### AEAT calendar: local and autonomic holidays extend, Modelo 369 does not

The AEAT 2026 taxpayer-calendar page says: "Si el vencimiento coincide con una festividad local o autonómica, el plazo finaliza el primer día hábil siguiente al señalado en este calendario, excepto para el modelo 369". The published dates are therefore already national-adjusted; the residual extension is autonomic or local. The same page scopes Modelo 360 to non-working days "en España". Fetched 2026-09-23.

### Ley 39/2015 art. 30.6 and 30.7: whose territory

Art. 30.6: "Cuando un día fuese hábil en el municipio o Comunidad Autónoma en que residiese el interesado, e inhábil en la sede del órgano administrativo, o a la inversa, se considerará inhábil en todo caso." Art. 30.7 makes each autonomous community's calendar include its municipalities' non-working days. Text verified in the consolidated BOE text and in the bundled corpus `src/cadrumo/_data/corpus/normatives/html/ley-39-2015.html`.

### LGT art. 48.2: fiscal domicile

Art. 48.2.a: for natural persons, habitual residence. The administration may instead take the place where activities are managed for persons mainly carrying on economic activities. Art. 48.2.b: for legal persons, the registered office where management is centralised. A declared residence is therefore the default coordinate for a resident natural person, not a proof for every autonomo.

### Registry vocabularies do not relate by name

Fact 0129 (`src/cadrumo/_data/registry/aeat/facts/0129-renta-ccaa-tax-residence-catalogue.toml`) has fifteen lower-case tokens with three-letter aliases. Fact 0143 (`src/cadrumo/_data/registry/aeat/facts/0143-deadline-calendar-territory-catalogue.toml`) has nineteen ISO 3166-2:ES territories. Member names differ for Balears (`BALEARES` against `ILLES_BALEARS`) and Valencia (`COMUNIDAD_VALENCIANA` against `VALENCIA`). No relation between the two exists in either fact.

### Current code

- `src/cadrumo/application/overview/calendar.py:858` passes no territory to the shift rule.
- The `HolidayJurisdiction` docstring in `src/cadrumo/domain/deadlines/festivos.py` claims AEAT ignores municipal holidays, contrary to the AEAT page.
- The typed profile answer in `src/cadrumo/domain/user_profile/setup_answers.py` defaults a missing tax-residence CCAA to the catalogue default.
- The registry holds national and autonomic holidays only (fact 0067); municipal holidays have no source.

### Registry holiday data does not match the official resolutions

The official per-territory non-working days come from the annual Secretaría de Estado de Función Pública resolution fixing the AGE calendar of días inhábiles: BOE-A-2023-23637 (2024), BOE-A-2024-26935 (2025) and BOE-A-2025-23702 (2026). Day names come from the Dirección General de Trabajo fiestas-laborales resolutions BOE-A-2023-22014, BOE-A-2024-21316 and BOE-A-2025-21667. Each id was fetched from boe.es and its title confirmed on 2026-09-23.

- Weekday counts: 2024 has 7 national and 58 regional entries; 2025 has 7 and 55; 2026 has 7 and 68. Weekend holidays are omitted because weekends are already non-working.
- Facts 0066 and 0067 (`src/cadrumo/_data/registry/aeat/facts/0066-holiday-calendar-publication.toml`, `0067-public-holiday.toml`) author regional days for only four territories. They have no 2026 publication at all, so every 2026 deadline falls back to calendar unavailable.
- They list 2025-11-10 as a Comunidad de Madrid regional day; neither 2025 resolution does, so it is municipal. They omit 2025-04-17 (Jueves Santo), which is regional in Madrid.
- Their cited `boe_url` for 2025, BOE-A-2024-22011, is an unrelated municipal job-competition notice.
- Canarias island holidays and the Val d'Arán swap of 26 December for 17 June are explanatory notes, not territory-wide days. Only days non-working throughout a territory can safely extend its residents' deadlines.

The fetched documents and a machine-readable extraction were produced in the session scratchpad and are not retained in the vault.

Not investigated: the seat-of-body branch for centralised AEAT units, and foral-territory filers who file with their foral hacienda.

## Sources

- https://sede.agenciatributaria.gob.es/Sede/ayuda/calendario-contribuyente/calendario-contribuyente-2026/recuerde/vencimientos-dias-inhabiles-sabados-festivos.html
- https://www.boe.es/buscar/act.php?id=BOE-A-2015-10565#a30
- https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a48
- https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-23637
- https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-26935
- https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-23702
- https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-21316
- `src/cadrumo/application/overview/calendar.py:858`
- `src/cadrumo/domain/deadlines/festivos.py`
