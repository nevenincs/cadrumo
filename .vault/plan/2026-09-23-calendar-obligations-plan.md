---
tags:
  - '#plan'
  - '#calendar-obligations'
date: '2026-09-23'
tier: L1
related:
  - '[[2026-09-23-calendar-obligations-holiday-jurisdiction-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
modified: '2026-09-23'
body_schema: body-v2
body_hash: 'sha256:0546feaa8de3745d5ded882b7d67e47987e99c7852000176fcdf2df45125eff1'
---

# `calendar-obligations` plan

Derive deadline holiday jurisdiction from registry data and prove calendar meaning through installed-wheel CLI and TUI processes.

## Description

Approved 2026-09-23 by the coordinator's CALENDAR-01 continuity brief, relayed for the operator, which names this bounded goal and its done conditions; the operator's standing instruction pre-approves plan phases.

S01 and S02 implement the accepted `2026-09-23-calendar-obligations-holiday-jurisdiction-adr`. S03 projects its coverage state under the accepted calendar integration and filing-semantics decisions. S04 replaces the in-process parity test with an installed-wheel driver following ACCEPTANCE-01, and S05 records gate evidence and the handoff. No other costly decision is involved. Live AEAT access, authentication, notification content, acknowledgement, response and submission remain excluded and NOT EXERCISED.

## Steps

- [x] `S01` - Author the tax-residence territory relation and art. 30.6 reference, validate and publish the authority; `src/cadrumo/_data/registry/aeat/facts/0143-deadline-calendar-territory-catalogue.toml, src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml, src/cadrumo/domain/calculations/registry/calendar_ccaa_catalogue.py and owning tests`.
- [x] `S02` - Resolve the deadline holiday territory from a declared resident common-regime residence and record typed holiday coverage on calendar entries; `src/cadrumo/domain/deadlines/models.py, profiles.py, festivos.py, src/cadrumo/application/overview/calendar.py, calendar_models.py and owning tests`.
- [x] `S03` - Project holiday coverage and translated shift reasons into the CLI and TUI calendar; `src/cadrumo/entrypoints/cli/_overview_payloads.py, _overview_rendering.py, src/cadrumo/application/modelo/declarations_calendar.py, src/cadrumo/entrypoints/tui/declarations/calendar.py, locales and owning tests`.
- [ ] `S04` - Replace in-process parity with an installed-wheel CLI/TUI calendar driver and sanitized receipt; `dev/acceptance/calendar/, dev/acceptance/income_tax/installed_tui_child.py and owning tests`.
- [ ] `S05` - Run type, lint and import gates on changed files and write the checkpoint and handoff; `.agents/session-briefs/handoffs/`.
- [x] `S06` - Re-author the 2024-2026 holiday facts from the AGE días-inhábiles resolutions and republish the authority; `src/cadrumo/_data/registry/aeat/facts/0066-holiday-calendar-publication.toml, 0067-public-holiday.toml, legal/dias-inhabiles-age.toml, corpus normatives and owning tests`.
- [x] `S07` - Persist and report the authority build identity so a stale generation names its drifted input, cut over with one queued republish; `src/cadrumo/domain/calculations/registry/authority_store.py, dev/registry/compiler/authority_database.py, dev/registry/pipeline/authority_publication.py and owning tests`.
- [x] `S08` - Stop the workbench calendar from re-deriving generation-constant data on every build; `src/cadrumo/application/overview/calendar_warnings.py, src/cadrumo/domain/deadlines/festivos.py and owning tests`.
- [x] `S09` - Resolve a static inspection's casilla labels in one locale-catalogue window; `src/cadrumo/core/i18n/locale_catalogue.py, src/cadrumo/application/modelo/workspace.py, workspace_producers.py and owning tests`.
- [ ] `S10` - Gate Modelo 136 on a declared unwithheld special-levy prize (LIRPF DA 33.7) so an undeclared profile is undetermined, not obliged, then refresh filing-calendar with a seed active through 2025; `src/cadrumo/_data/registry/aeat/facts/0139-modelo-payer-applicability-facts.toml, modelos/136 applicability, user_profile schema.toml, domain/deadlines profiles, docs/_sequences seeds and filing-calendar goldens`.

## Parallelization

Steps run sequentially under one writer. S01 and S02 share the published authority generation; S03 depends on the S02 contract; S04 builds its wheel from the committed S01-S03 source. Registry holiday-data research may run in a read-only helper that writes only to the session scratchpad.

## Verification

Each Step passes its focused owning tests with `-n0` and explicit markers, plus Ruff, format, ty, basedpyright strict and pyrefly on its changed files. S01 also proves candidate validation, source installation and publication of the authority separately. S04 passes one installed-wheel run whose sanitized receipt records source commit, wheel SHA-256, authority generation and installed package identity. The import gate is reported with calendar-sourced findings counted separately from the pre-existing baseline.
