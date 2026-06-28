---
tags:
  - '#plan'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
tier: L2
related:
  - '[[2026-06-03-m200-internal-casilla-discipline-adr]]'
  - '[[2026-06-03-m200-internal-casilla-discipline-research]]'
  - '[[2026-06-02-modelo-200-base-determination-adr]]'
---


# `m200-internal-casilla-discipline` `Modelo 200 internal-only casilla discipline: schema field, gate exemption, bin-aplicada-maxima migration` plan

Land a CasillaDefinition.internal_only schema field and matching gate exemption so app-internal computed casillas (LIS art. 26.1 BIN ceiling and successors) declare their intent at the registry source and clear the calculation-closure gates without per-casilla allowlists.

## Description

This plan executes the accepted `m200-internal-casilla-discipline` ADR. The decision is to add a single `internal_only: bool = False` field to `CasillaDefinition` in `src/aeat/domain/calculations/registry/_schema.py`, route around it in `derive_calculation_completeness_casillas` (`src/aeat/domain/calculations/registry/_record_design.py`), and migrate the M200 `DP200014:bin-aplicada-maxima` casilla TOML to declare the flag. The change clears three reds in `src/aeat/domain/calculations/registry/test_record_design.py` (the `registered_record_design_sources`, `calculation_completeness_manifests`, and `calculation_closure_bounds_the_full_diseno_coverage` gates) introduced when the M200 base-determination ADR landed the LIS art. 26.1 BIN-compensation ceiling as a synthetic computed casilla absent from the AEAT-published Diseno de Registros. The plan also lands two anti-tautology tests defending the schema validator: a casilla declaring `internal_only=true` with non-empty `export_refs`, or with `input_kind != COMPUTED`, MUST raise `RegistryValidationError` at registry load. The parent ADR (`2026-06-02-modelo-200-base-determination-adr`) is the substantive authority for the bin-aplicada-maxima ceiling and the BLOCKING `cap_le_when_positive` predicate that consumes it; this plan ships the registry discipline that lets that work pass the calculation-registry gates without weakening them.

## Steps

### Phase `P01` - Schema field on CasillaDefinition

Add the internal_only boolean field to CasillaDefinition with default False, plus a model_validator refusing internal_only=true with non-empty export_refs or non-computed input_kind.

- [x] `P01.S01` - add the internal_only bool field to CasillaDefinition with default False and a description naming the contract; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P01.S02` - extend the CasillaDefinition model_validator chain to refuse internal_only=true with non-empty export_refs (incoherence: app-internal casilla cannot also be exported); `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P01.S03` - extend the CasillaDefinition model_validator chain to refuse internal_only=true with input_kind != COMPUTED (incoherence: internal ceiling must be formula-derived); `src/aeat/domain/calculations/registry/_schema.py`.

### Phase `P02` - Gate exemption in derive_calculation_completeness_casillas

Build the internal_only identity set from the revision and short-circuit the Diseno-presence check for those pairs while preserving the segment-carrying identity in the derived manifest.

- [x] `P02.S04` - build the internal_only identity frozenset from revision.casillas at the start of derive_calculation_completeness_casillas; `src/aeat/domain/calculations/registry/_record_design.py`.
- [x] `P02.S05` - in the multi-segment branch short-circuit the Diseno-presence check for internal_only pairs while appending the segment-carrying DerivedDisenoCasilla to the manifest; `src/aeat/domain/calculations/registry/_record_design.py`.

### Phase `P03` - M200 migration and anti-tautology tests

Flip internal_only=true on the bin-aplicada-maxima casilla TOML to clear the three reds and author the anti-tautology tests that defend the schema validator.

- [x] `P03.S06` - flip internal_only=true on the bin-aplicada-maxima casilla TOML; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-bin-aplicada-maxima.toml`.
- [x] `P03.S07` - author the anti-tautology test asserting CasillaDefinition(internal_only=True, export_refs=(some_export_id,)) raises RegistryValidationError; `src/aeat/domain/calculations/registry/test_internal_only_casilla.py`.
- [x] `P03.S08` - author the anti-tautology test asserting CasillaDefinition(internal_only=True, input_kind=MANUAL) raises RegistryValidationError; `src/aeat/domain/calculations/registry/test_internal_only_casilla.py`.
- [x] `P03.S09` - re-run the three formerly-red gates to confirm clear closure and assert the M200 manifest still carries the bin-aplicada-maxima identity post-exemption; `src/aeat/domain/calculations/registry/test_record_design.py`.

## Parallelization

Phases are strictly sequenced: P02 depends on the schema field landing in P01 (the gate exemption reads `casilla.internal_only`, which does not exist until P01.S01 commits); P03 depends on both the schema field (the bin-aplicada-maxima TOML migration in P03.S06 sets a field that must already exist, and the anti-tautology tests in P03.S07-S08 exercise validators authored in P01.S02-S03) and the gate exemption (P03.S09 re-runs the formerly-red gates, which only clear once P02 short-circuits the Diseno check). Within P01, S02 and S03 may be authored in parallel because both extend the existing model_validator chain on distinct conditions and do not collide. Within P02, S04 and S05 are inherently sequential because S05 consumes the identity frozenset S04 builds. Within P03, S06 and S07-S08 may be authored in parallel (TOML edit and new test file are independent), but S09 (the gate re-run assertion) MUST land last in the commit so the closure-clear evidence is observed against the final state.

## Verification

The plan is complete when (a) every Step in P01, P02, and P03 is closed (`- [x]`); (b) `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_record_design.py -q` reports the three formerly-red gates green (`test_registered_record_design_sources_are_discovered_and_parseable`, `test_calculation_completeness_manifests_match_their_calculation_surface`, `test_calculation_closure_bounds_the_full_diseno_coverage`); (c) `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_internal_only_casilla.py -q` is green, with both anti-tautology tests (P03.S07 and P03.S08) explicitly asserting `RegistryValidationError` rather than catching a generic exception; (d) the M200 calculation-completeness manifest still enumerates `(DP200014, DP200014:bin-aplicada-maxima)` as a derived identity post-exemption, proving the casilla retained its calc-graph role; (e) `uv run --no-sync pytest --collect-only -q` reports clean collection across the full registry suite immediately before commit; (f) the change ships as one atomic explicit-path commit per `aeat-architecture-boundaries` relocation/atomicity discipline, tagged in the subject line with `schema:CasillaDefinition.internal_only`. A red anti-tautology test (the validator accepts an incoherent casilla) blocks closure; a red M200 gate (the closure no longer enumerates bin-aplicada-maxima) also blocks closure.
