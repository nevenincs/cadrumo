---
tags:
  - '#research'
  - '#modelo-202-obligation'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:b9cb3d9d8091c4c8e8bd8d0819bda4d6a336aba7597770c048f42da7664a15f6'
related: []
---

# `modelo-202-obligation` research: `Modelo 202 filing obligation legal grounding`

Question: from which facts can Cadrumo decide, per instalment, whether a sociedad at or below the LIS art. 40.3 INCN threshold must file a Modelo 202? Today the calendar answers INCOMPLETE for every such instalment because the profile holds neither the art. 40.2 base nor the art. 40.3 election (`src/cadrumo/domain/calculations/registry/applicability_modelo202.py:233-279`). Conclusion: the law makes the obligation turn on whether an ingreso results; the art. 40.2 base is a figure of an earlier Modelo 200 that the registry already binds per instalment; the art. 40.3 election is a censal declaration that persists until renounced. Two questions remain open.

## Findings

### LIS art. 40.1: who pays, when, and who is excluded

The pago fraccionado is due in the first 20 natural days of April, October and December, on account of the periodo impositivo in course on day 1 of that month. The entities of LIS art. 29.4 and 29.5 neither pay it nor file the declaration (`src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-40.html.extracted.md:3-4`). Art. 29.4 lists entities taxed at 1 per cent and art. 29.5 the fondos de pensiones taxed at 0 per cent (`src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html:4813`, `:4832`). The per-article extract `ley-27-2014-art-29.html.extracted.md` omits paragraphs 4 and 5, an extraction loss; the full-law file carries them. The profile has no fact that identifies these entities.

### LIS art. 40.2: the base is fixed by an earlier return, per instalment

The base is the cuota integra of the last periodo impositivo whose declaration deadline had passed on the first of the 20 days of the instalment window, less deducciones, bonificaciones, retenciones and ingresos a cuenta of that period. The payment is 18 per cent of the base (`ley-27-2014-art-40.html.extracted.md:5`, `:7`). When the last concluded period is shorter than a year, a proportional part of earlier cuotas completes 12 months (`:6`). A base of zero or less yields no ingreso.

### LIS art. 40.3: the election, its persistence, and the threshold

The election is made in the declaracion censal in February of the first calendar year it covers, or within two months of the start of a non-calendar periodo impositivo, or by the end of the first instalment window if that is shorter (`ley-27-2014-art-40.html.extracted.md:10`). It binds that periodo impositivo and the following ones until renounced in a later declaracion censal within the same windows (`:11`). It is mandatory when the INCN exceeded 6 million euros in the 12 months before the start of the periodo impositivo the instalment belongs to (`:12`). The payment is computed on the running base imponible of 3, 9 or 11 months (`:8`, `:13`), which no earlier return supplies.

### Orden HFP/227/2017 art. 1.3: filing follows the ingreso below the threshold

Filing Modelo 202 is mandatory above the 6 million euro INCN threshold. For other entities, filing is not mandatory in an instalment where no ingreso results (`src/cadrumo/_data/corpus/normatives/html/orden-hfp-227-2017.html.extracted.md:9-10`). Resident-only AIE and UTE under LIS title VII chapter II never file it (`:11`), and grupos fiscales use Modelo 222 instead (`:8`). The registry catalogue already cites the threshold and no-ingreso sentences (`src/cadrumo/_data/registry/aeat/facts/0101-modelo-202-applicability-catalogue.toml:14-23`).

### The registry already binds the art. 40.2 base

`modelo-202-cuota-base-ejercicio-anterior` copies Modelo 200 casilla `DP200014B:00599`, the cuota del ejercicio a ingresar o a devolver, which is the cuota liquida less retenciones and ingresos a cuenta. Its temporal member uses `filing_year_offset_by_target_period` with offsets 1P two years back and 2P and 3P one year back, source period `0A` (`src/cadrumo/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/bindings/0001-declarations.toml:33-44`; rationale in the comment at `:1-32`). It is declared only at the `2025-y-siguientes` edition. Its comment states that the earlier instructions carry the same art. 40.2 wording and that no Modelo 200 revision is authored before 2024, so an early 1P anchor resolves to no value. The dependency classification treats the source as factual evidence (`src/cadrumo/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/dependency_classifications/0001-declarations.toml`).

### Existing attestation, declaration-state and schema mechanisms

- `ATTEST_PRIOR_VALUE` exists (`src/cadrumo/application/modelo/edit_models.py:144`, admission at `src/cadrumo/application/modelo/edit_admission.py:220-257`). The accepted 2026-11-11 amendment admits it on scalar relation-prefill dependencies whenever no upstream return is held; the base binding is such a dependency.
- Profile facts carry `valid_from` and `valid_to` (`src/cadrumo/domain/user_profile/values.py:231-263`). The INCN field is effective-dated (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:460-467`). The schema is at version 8 (`schema.toml:3`), and new paths were introduced by a version bump before (`src/cadrumo/domain/user_profile/schema_migration.py:124-143`).
- The cross-period clean-state gate relaxes only a same-year `app_filing` chain; a cross-year local filing stays blocking (`src/cadrumo/application/calculations/cross_period_clean_state.py:298-319`).

### Refinements to the lane proposal

1. Base timing: the source period is fixed on the first day of the instalment window (1 April, October, December), not at the start of the 202 period, so 1P reads an earlier Modelo 200 than 2P and 3P. The binding offsets already encode this for a calendar periodo impositivo.
2. Absent election: under the accepted payer-fact declaration-state contract an absent fact is never-asked, so only a stated no can select art. 40.2.
3. Persistence: the election binds until a renuncia, so the fact needs an end, expressible as a later dated value.
4. Elected branch: with the election made and INCN at or below the threshold, whether an ingreso results depends on the running base imponible, which neither the profile nor a Modelo 200 holds.
5. Threshold window: the INCN is measured over the 12 months before the start of the periodo impositivo, not before the instalment.

A further observation: `2026-06-19-m202-first-period-attestation-adr` keys its suppression on the activity-start year being at or after the target year, but the second-year 1P also has no art. 40.2 base, because the first-year Modelo 200 deadline has not passed on 1 April.

### Open items

- Not investigated: whether a captured censal observation (certificado de situacion censal, or the censal parser) exposes the art. 40.3 option. If it does, `2026-06-05-live-censo-calendar-reconciliation-adr` would place capture ahead of the profile.
- Not verified: the binding comment claim that every earlier Modelo 202 edition carries the same art. 40.2 wording; the instructions of each edition were not read.
- Not covered by any profile fact: non-calendar periodos impositivos (the offsets assume a calendar one) and the art. 40.2 proportional completion for a short last period.

## Sources

- LIS, Ley 27/2014, BOE-A-2014-12328: https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328
- `src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-40.html.extracted.md:3-13`
- `src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html:4813`, `:4832` (art. 29.4 and 29.5)
- Orden HFP/227/2017, BOE-A-2017-2778: https://www.boe.es/buscar/act.php?id=BOE-A-2017-2778
- `src/cadrumo/_data/corpus/normatives/html/orden-hfp-227-2017.html` and `orden-hfp-227-2017.html.extracted.md:8-11` (art. 1.2 and 1.3)
- `src/cadrumo/_data/registry/aeat/facts/0101-modelo-202-applicability-catalogue.toml:14-23`
- `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/bindings/0001-declarations.toml:1-44`
- `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/dependency_classifications/0001-declarations.toml`
- `src/cadrumo/domain/calculations/registry/applicability_modelo202.py:233-279`
- `src/cadrumo/application/modelo/edit_models.py:144`; `src/cadrumo/application/modelo/edit_admission.py:220-257`
- `src/cadrumo/domain/user_profile/values.py:231-263`; `src/cadrumo/domain/user_profile/schema_migration.py:124-143`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:3`, `:460-467`
- `src/cadrumo/application/calculations/cross_period_clean_state.py:298-319`
