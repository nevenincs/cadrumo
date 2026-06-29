---
tags:
  - '#plan'
  - '#trabajador-del-mar'
date: '2026-05-31'
modified: '2026-06-29'
tier: L3
related:
  - '[[2026-05-31-trabajador-del-mar-adr]]'
  - '[[2026-05-31-trabajador-del-mar-research]]'
---


# trabajador-del-mar W01-W03 plan

## Wave `W01` - registry and profile-fact foundation

Establishes the data layer: profile fact schema extension and registry TOML binding
entries for all three exemption variants. W02 depends on W01 being merged; the binding
entries must exist before the engine can resolve them.

### Phase `W01.P01` - profile-fact schema extension

Adds the worker_class profile fact to the registry profiles TOML and verifies the
schema accepts it without breaking existing profiles.

- [x] `W01.P01.S01` - add worker_class fact enum with value trabajador_del_mar to the 2025 profiles TOML; `src/aeat/_data/registry/aeat/categories/profiles/2025.toml`.
- [x] `W01.P01.S02` - add vessel_flag, waters_type, vessel_registry, and retmar_registered supporting facts to the 2025 profiles TOML; `src/aeat/_data/registry/aeat/categories/profiles/2025.toml`.
- [x] `W01.P01.S03` - write a registry-load test asserting the new profile facts appear in the validated snapshot without schema error; `src/aeat/domain/calculations/registry/test_trabajador_del_mar_profile.py`.

### Phase `W01.P02` - registry binding entries

Adds the trabajador_del_mar category TOML with all three exemption binding entries
and confirms referential integrity on snapshot build.

- [x] `W01.P02.S04` - create trabajador_del_mar.toml with Art. 7.p) binding entry (cap=60100, daily_rate formula, legal_refs=Ley 35/2006 Art. 7.p) BOE-A-2006-20764); `src/aeat/_data/registry/aeat/categories/trabajador_del_mar.toml`.
- [x] `W01.P02.S05` - add REBECA binding entry (exempt_fraction=0.50, legal_refs=Ley 19/1994 Arts. 73.2 73.3 75.1 75.3 BOE-A-1994-15794); `src/aeat/_data/registry/aeat/categories/trabajador_del_mar.toml`.
- [x] `W01.P02.S06` - add DA 41 binding entry (exempt_fraction=0.50, status=inactive_pending_eu_clearance, legal_refs=Ley 35/2006 DA 41 BOE-A-2006-20764 and Ley 6/2018 BOE-A-2018-9268); `src/aeat/_data/registry/aeat/categories/trabajador_del_mar.toml`.
- [x] `W01.P02.S07` - write registry snapshot integrity test asserting all three binding entries resolve with legal_refs populated; `src/aeat/domain/calculations/registry/test_trabajador_del_mar_profile.py`.

## Wave `W02` - calculation engine integration

Wires the binding selector and implements the three exemption calculations. Depends on
W01 binding entries existing in the validated snapshot.

### Phase `W02.P03` - binding selector

Extends the binding-resolution logic in domain/renta/ to branch on worker_class and
the vessel/waters supporting facts.

- [x] `W02.P03.S08` - add art_7p_eligible predicate to the binding selector (vessel_flag != ES AND waters_type == international); `src/aeat/domain/renta/`.
- [x] `W02.P03.S09` - add rebeca_eligible predicate to the binding selector (vessel_registry == REBECA OR scheduled_canary_route); `src/aeat/domain/renta/`.
- [x] `W02.P03.S10` - add da41_eligible predicate as future/inactive gate (tuna_fleet AND pending_eu_clearance); `src/aeat/domain/renta/`.
- [x] `W02.P03.S11` - write selector unit tests covering art_7p_eligible true/false, rebeca_eligible true/false, da41_eligible inactive-guard raises domain error; `src/aeat/domain/renta/`.

### Phase `W02.P04` - exemption calculations

Implements the three calculation functions and wires them to produce CasillaObservation
rows with full provenance.

- [x] `W02.P04.S12` - implement Art. 7.p) calculation (exempt_amount = min(annual_salary / 365 * qualifying_days, 60100)), output as CasillaObservation with legal_refs from registry binding; `src/aeat/domain/renta/`.
- [x] `W02.P04.S13` - implement REBECA calculation (exempt_amount = gross_navigation_income * Decimal(0.50)), output as CasillaObservation with legal_refs from registry binding; `src/aeat/domain/renta/`.
- [x] `W02.P04.S14` - implement DA 41 guard raising MaritimeExemptionInactiveError if da41_eligible resolves True; `src/aeat/domain/renta/`.
- [x] `W02.P04.S15` - implement RETMAR mandatory-filing status check raising ProfileCompletenessWarning (not a calculation gate) when retmar_registered=True; `src/aeat/domain/renta/`.
- [x] `W02.P04.S16` - write calculation tests using registry-authoritative fixture values for Art. 7.p) and REBECA; `verify CasillaObservation.legal_refs populated end-to-end; `src/aeat/domain/renta/`.

### Phase `W02.P05` - application layer wiring

Connects the calculation results through application/calculations/ to the CLI emit path,
preserving typed observations.

- [x] `W02.P05.S17` - wire trabajador_del_mar calculation output through the application calculations service preserving CasillaObservation list alongside flat casilla_values; `src/aeat/application/calculations/`.
- [x] `W02.P05.S18` - write integration test asserting CLI JSON emit includes legal_refs and source_refs for each maritime exemption CasillaObservation; `src/aeat/application/calculations/`.

## Wave `W03` - CLI surface and locales

Exposes the new worker class selector and exemption labels to operators via the CLI
and adds locale strings. Depends on W02 being merged.

### Phase `W03.P06` - locale keys

Adds locale strings for the worker class selector, each exemption variant label, and
the RETMAR mandatory-filing warning.

- [x] `W03.P06.S19` - scaffold locale keys for worker_class selector and trabajador_del_mar value; `python -m aeat.locales scaffold`.
- [x] `W03.P06.S20` - scaffold locale keys for art_7p exemption label, rebeca exemption label, da41 inactive label, and retmar_mandatory_filing warning; `python -m aeat.locales scaffold`.
- [x] `W03.P06.S21` - add Spanish (es) locale translations for all new keys added in S19-S20; `locales/es.yml`.
- [x] `W03.P06.S22` - run locale audit to confirm no orphan or missing keys; `python -m aeat.locales audit`.

### Phase `W03.P07` - CLI surface verification

Confirms the new profile fact is accepted by the CLI input path and that the RETMAR
warning surfaces in operator-facing output.

- [x] `W03.P07.S23` - verify CLI accepts worker_class = trabajador_del_mar in the config input path without validation error; `src/aeat/entrypoints/cli/`.
- [x] `W03.P07.S24` - verify CLI JSON output for a trabajador_del_mar profile includes maritime exemption CasillaObservation rows with legal_refs; `src/aeat/entrypoints/cli/`.
- [x] `W03.P07.S25` - verify RETMAR mandatory-filing warning appears in CLI output when retmar_registered = True; `src/aeat/entrypoints/cli/`.

## Closure note -- 2026-06-01

Plan complete: 25 of 25 Steps closed across 3 Waves / 7 Phases.
Twenty `Step Record` artefacts persisted under
`.vault/exec/2026-05-31-trabajador-del-mar/`; the four W03.P06 locale
Steps and the three W03.P07 CLI-verification Steps were bundled into
two combined records (`-W03-P06-S19-S22.md`, `-W03-P07-S23-S25.md`)
per the locale-scaffold + CLI-verification merge convention.
Registry-side foundation, profile-fact wiring, calculation entries
(Art. 7.p exemption, REBECA exemption, DA 41 inactivity), locale
parity (es full; ca/en/hu via scaffold + audit), and CLI-output
verification (CasillaObservation legal_refs + RETMAR warning) all
landed. Phase summaries are deferred to the next vault-curation
cadence; plan-level closure is asserted via the 20 exec records and
the unbroken `[x]` row state.
