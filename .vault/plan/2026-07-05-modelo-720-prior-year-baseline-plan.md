---
tags:
  - '#plan'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
tier: L3
related:
  - '[[2026-06-02-modelo-720-prior-year-baseline-adr]]'
  - '[[2026-06-02-modelo-720-prior-year-baseline-research]]'
  - '[[2026-07-05-modelo-720-prior-year-baseline-adr]]'
  - '[[2026-07-05-modelo-720-row-carrier-adr]]'
---

# `modelo-720-prior-year-baseline` plan

## Wave `W01` - M720 obligation-block threshold

Correct the live M720 aggregation gate so declarability follows the RD 1065/2007 obligation blocks rather than raw enum classes, then verify the row projection remains registry-backed.

### Phase `W01.P01` - Threshold behavior repair

Land and verify the narrow application-layer fix that sums securities and insurance within the shared valores, derechos, seguros, and rentas obligation block.

- [x] `W01.P01.S01` - Repair M720 declarability to aggregate present classes by regulatory obligation block before applying the strict declaration floor; `src/aeat/application/aggregation/_foreign_assets.py`.
- [x] `W01.P01.S02` - Add real-behavior aggregation and per-modelo resolver gates for mixed security and insurance rows crossing the shared block floor; `src/aeat/application/aggregation/tests/test_foreign_assets.py`.
- [x] `W01.P01.S03` - Clean stale threshold-axis authority comments so future workers do not reintroduce per-class semantics; `src/aeat/core/external_constants.py`.
- [x] `W01.P01.S04` - Clean stale threshold-axis enum documentation so raw classes are not described as independent floors; `src/aeat/core/aggregation.py`.
- [x] `W01.P01.S05` - Clean stale threshold-axis obligation-layer documentation so the application gate is described as block-based; `src/aeat/core/_foreign_asset_obligation.py`.
- [x] `W01.P01.S06` - Clean stale threshold-axis row-binding comments so registry helpers point to obligation-block semantics; `src/aeat/domain/calculations/registry/_detail_record_bindings.py`.
- [x] `W01.P01.S07` - Clean stale threshold-axis registry comments beside the M720 deadline-window scaffold; `src/aeat/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/deadline_windows/0001-deadline_windows.toml`.

## Wave `W02` - M720 class-code taxonomy

Resolve the official M720 clave taxonomy so typed foreign-asset observations cannot silently export real estate as IIC or leak Modelo 721 virtual-currency codes into Modelo 720.

### Phase `W02.P02` - Taxonomy decision

Ground the BOE and AEAT class-code authority, decide whether M720 needs a distinct IIC class and whether virtual currency must split to a Modelo 721-specific taxonomy, then record the decision before code migration.

- [x] `W02.P02.S08` - Author the M720 class-code taxonomy ADR covering B real estate, I IIC, V securities, S insurance, and the Modelo 721 virtual-currency split; `.vault/adr/`.

### Phase `W02.P03` - Typed projection migration

Apply the approved taxonomy to the typed aggregation-to-row projection and add tests that prove the emitted fichero class code is official for each supported M720 asset category.

- [x] `W02.P03.S09` - Migrate the typed M720 asset-code map so real estate emits B and unsupported or split-out classes cannot emit the wrong record-design clave; `src/aeat/application/aggregation/_foreign_assets.py`.
- [x] `W02.P03.S10` - Update the central foreign-asset class taxonomy tests to pin the official M720 clave set and any Modelo 721 split; `src/aeat/core/tests/test_foreign_asset_obligation.py`.
- [x] `W02.P03.S11` - Add M720 row-projection tests proving real estate emits B and virtual currency cannot be emitted through Modelo 720; `src/aeat/application/aggregation/tests/test_foreign_assets.py`.

## Wave `W03` - M720 row-carrier mesh promotion

Design and implement a row-indexed source-mesh carrier before foreign_asset is promoted out of deferral, preserving the registry row-binding contract and avoiding scalar binding overclaim.

### Phase `W03.P04` - Row-carrier decision

Decide the row-indexed binding-value carrier for M720 detail rows, comparing a first-class row map with typed detail rows and rejecting scalar synthetic ids.

- [x] `W03.P04.S12` - Author the M720 row-carrier ADR deciding how row-indexed binding values flow through the source mesh and export draft surfaces; `.vault/adr/`.

### Phase `W03.P05` - Source-mesh envelope implementation

Implement the approved row carrier in the aggregation source-mesh envelope and merge path before enrolling the foreign-asset resolver.

- [x] `W03.P05.S13` - Add the approved row-indexed M720 carrier to the calculation source resolution envelope; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W03.P05.S14` - Return validated M720 row-indexed binding values from the foreign-assets aggregation resolver through the approved carrier; `src/aeat/application/aggregation/_foreign_assets.py`.
- [x] `W03.P05.S15` - Carry row-indexed mesh values into modelo draft and export replay without flattening them into scalar binding ids; `src/aeat/application/modelo/_calculation_resolution.py`.

### Phase `W03.P06` - Foreign-asset enrollment

Promote foreign_asset from deferred to enrolled only after the row carrier proves live mesh parity against the prior aggregation output.

- [x] `W03.P06.S16` - Enroll the foreign-assets resolver in the live calculate mesh only after row-carrier parity gates pass; `src/aeat/application/modelo/_calculation_actions.py`.
