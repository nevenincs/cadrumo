---
tags:
  - '#audit'
  - '#linkage-design-audit'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
  - "[[2026-05-16-linkage-design-audit-audit]]"
  - "[[2026-05-17-linkage-design-audit-audit]]"
  - "[[2026-05-18-linkage-design-audit-audit]]"
  - "[[2026-05-26-linkage-design-audit-research]]"
  - "[[2026-05-26-linkage-design-audit-adr]]"
  - "[[2026-05-17-linkage-design-audit-plan]]"
---

# `linkage-design-audit` audit: `wave-3-close-out-after-p02-collapse`

Close-out audit for the linkage-design-audit plan after the Wave 3
P02 typed-observation collapse landed across the three primary
cross-boundary models. Tracks plan rows `P02.S05` through
`P02.S11`, `P08.S35` through `P08.S39`, and `P07.S32`–`S34`.

## Scope

This audit covers the work landed since the previous close-out
audit (`2026-05-18-linkage-design-audit-audit`). The previous
close-out reported `48 of 102 inventory rows verified (47%)`; the
re-audit it ran flagged `R003`, `R004`, `R005` as regressed
(typed-observation envelope landed alongside the flat mapping but
not as canonical storage on `RegistryCalculationResult` or
`CalculationRevision`).

This audit verifies the resolution of those three regressions and
records the staged-path decision for the `CalculationRevision`
field collapse.

## Findings

### Severity: informational — Wave 3 P02 collapse landed

**`R002` RegistryFilingObservation/Modelo collapse** — already
verified by the prior close-out as the canonical pattern
(`casilla_values` is a derived `@property` over the typed
`observations` tuple). Re-confirmed in `_bindings.py:117-127`.
No regression.

**`R003`/`R005` RegistryCalculationResult collapse** — landed at
commit `6963600c0` (plan row `P02.S08`). `RegistryCalculationResult`
now stores `observations: tuple[CasillaObservation, ...]`
canonically; `values` and `entries` become derived `@property`
views. `CasillaObservation` extended with `op: str | None` so the
`RegistryCalculationEntry` projection round-trips losslessly.
Schema-hardening W09 hygiene gates (W09.P20.S139 + S140) plus
`test_casilla_observation.py` (6/6 green) plus
`test_formula_runtime.py` (15/15 green) confirm the canonical
shape lands without disturbance.

**`R004` CalculationRevision collapse** — landed at commit
`309909260` (plan rows `P02.S09` + `P08.S37` + `P08.S39`) per the
staged-path decision in ADR `2026-05-26-linkage-design-audit-adr`.
Stage one: typed `observations` envelope is the logical source of
truth; the flat `casilla_values` field is enforced equal to the
projection of `observations` at construction time
(`_outputs_for_hash_from_observations` helper plus
`ModeloValidationError` on drift). Stage two (drop the flat field
+ JSON-schema migration) deferred to a separate ADR after one
release cycle.

The hash-stability pin (`P08.S35`, SHA-256
`5b78dd04…`) is the regression anchor. It stayed green across all
three landings, proving the projection is byte-identical to the
historical hash domain. The content-addressed identity invariant
is preserved.

### Severity: informational — supporting infrastructure landed

**Cross-module-import resolution gate** (schema-hardening W09.P20
S139 + S140). Closes the foreign-WIP-adds-import-without-export
pattern that surfaced three times during the P02.S08 landing.
`test_cross_module_imports_resolve.py` runs against 12,897 import
triples; 4 baseline entries track the in-flight
`live-iva-compensation-wallet` campaign's repair_integrity backend.
Sibling `__init__.py` cap baseline (S140) caps 146 public-imports-
not-in-`__all__` across 16 `__init__.py` files; cap-burndown
tracked as a slow drip outside this epic.

**No-synthetic-sede fixture sweep** (schema-hardening W09.P19).
4 candidate files audited for `synthetic_data_allowed=true` +
AEAT-host pairs after the no-synthetic-sede-live-surfaces ADR
landed. One file migrated (`test_authenticated_simulator_surface`);
three already correctly authored. No dict-literal form anywhere
in the codebase.

**M303 directory-layout migration** (schema-hardening W08.P18.S135).
Resolved a dual-layout `RegistryLoadError` collision that surfaced
during the P02.S08 landing. 6,931-line flat `303.toml` replaced
with the canonical directory layout matching the 10 other
directory-mode modelos. Test parity proved across 52 tests
(test_modelo_303_registry, test_formula_runtime,
test_loader_directory_mode).

### Severity: medium — Wave 3 P05 still open

The CLI legal-grounding surfacing phase (`P05.S24`–`P05.S28`) is
the remaining unbuilt slice of the Wave 3 plan. Five steps cover
adopting `SchemaEnvelope` at modelo work-lifecycle commands,
adding typed context keys to `RegistryValidationError` and
`RegistrySnapshotError`, implementing the `--explain` flag that
surfaces `legal_refs` per the existing ADR convention, and
exposing `legal_refs` on review-queue findings. Not blocked by
P02; can be picked up independently as a CLI-surface campaign.

### Severity: low — Wave 3 P06 record-spec coverage already landed

The hand-authored record-spec structural-coverage phase
(`P06.S29`–`P06.S31`) verified per the prior close-out audit:
parametrised pytest covers byte-length integrity and casilla-id
resolution against the registry snapshot; `reference` field on
`RecordFieldSpec` exists. Closed; no new work.

### Severity: low — Wave 3 P03 + P04 already landed

Discriminated selector unions (`P03.S12`–`P03.S15`) and
hexagonal-direction enforcement (`P04.S16`–`P04.S23`) ticked in
the prior close-out audit; verified via `.importlinter` and
schema-level union types. No regression in this audit.

### Severity: low — superseded plan rows

`P02.S10` and `P08.S38` (libcst codemod over 27 construction
sites) were superseded by the ADR's staged path: stage one keeps
the `casilla_values=` constructor kwarg unchanged, so no codemod
migration is required today. Codemod work resurfaces inside the
future stage-two ADR (`casilla-values-flat-field-retirement`)
when the actual field signature changes.

## Recommendations

- **Treat the linkage Wave 3 P02 collapse as closed.** Three
  primary cross-boundary models (`RegistryFilingObservation`,
  `RegistryCalculationResult`, `CalculationRevision`) now carry
  the typed `observations` envelope as the logical source of
  truth. The flat `casilla_values` fields persist on the wire on
  `CalculationRevision` only (per the staged path) and are
  enforced consistent at construction time.
- **Schedule the stage-two ADR** (`casilla-values-flat-field-retirement`)
  after one release cycle of stage one running in production.
  The ADR's risks-accepted section documents the one-cycle dual-
  persistence window; gathering production evidence over that
  window is the right input to the stage-two migration design.
- **Pick up Wave 3 P05** (CLI legal-grounding surfacing) as the
  next linkage-design-audit slice. It is self-contained and the
  ADR convention for the `--explain` flag is already established.
  Five steps (`S24`–`S28`) cover the full scope.
- **Keep the schema-hardening W09.P20 hygiene gates running** as
  the continuous-hardening surface for foreign-WIP regressions.
  The 146-finding `__init__.py` cap baseline is technical debt
  to drip-burn; the gate prevents drift in either direction.
- **Do not touch the live-iva-compensation-wallet repair_integrity
  surface from this branch.** That backend is the other
  campaign's in-flight work; cross-campaign scaffolding would
  contaminate two parallel plans.

## Plan linkage

Closes:
- `P02.S05`, `P02.S06`, `P02.S07`, `P02.S08`, `P02.S09`,
  `P02.S10`, `P02.S11` (Wave 3 typed envelope collapse)
- `P08.S35`, `P08.S36`, `P08.S37`, `P08.S38`, `P08.S39`
  (hash-stability pre-flight + ADR + stage-one execution +
  roundtrip verification)
- `P07.S33` (feature index regenerated via
  `vaultspec-core vault feature index --feature linkage-design-audit`)
- `P07.S34` (this audit document)

Remains open inside the linkage-design-audit plan:
- `P05.S24`–`P05.S28` (CLI legal-grounding surfacing) —
  unblocked; ready for next slice
- `P07.S32` (linkage health dashboard re-run) — deferred; no
  scratch tooling is committed for the dashboard right now and
  the scripted re-audit is out of scope without that infrastructure
