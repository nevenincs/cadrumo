---
tags:
  - '#plan'
  - '#modelo-130-relation-regression'
date: '2026-05-26'
tier: L2
related:
  - '[[2026-05-26-modelo-130-relation-regression-adr]]'
  - '[[2026-05-26-modelo-130-relation-regression-audit]]'
  - '[[2026-05-19-modelo-130-relation-regression-research]]'
  - '[[2026-05-19-modelo-130-relation-regression-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `modelo-130-relation-regression` `selector-max-year-delta-and-bound-casilla-zero-default-remediation` plan

### Phase `P01` - same-ejercicio selector capability

Add the `max_year_delta` field to `_PreviousModeloSelector` and its
anchor-drop semantics, without flipping runtime defaults or revising
any binding.

- [x] `P01.S01` - add the `max_year_delta: int | None = None` field to `_PreviousModeloSelector` with pydantic validation rejecting negative values; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `P01.S02` - extend `_PreviousModeloSelector.required_period_anchors_for_target` to drop anchors whose `period_year_delta` is strictly greater than `max_year_delta` when the cap is set; `the empty-anchor return path is preserved; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `P01.S03` - add unit tests for the cap: cap unset preserves prior behaviour, cap = 0 admits same-year anchors only, cap = 0 with offset = -1 against target = "1T" returns empty anchors, negative cap is rejected by the field validator; `src/aeat/domain/calculations/registry/test_formula_runtime.py`.
- [x] `P01.S04` - extend `previous_filing_observation_requirements` and `resolve_previous_filing_binding_values` so the empty-anchor return path produces no requirement and no resolved value for the affected binding; `assert by a new test that requirements walk for a cap-suppressed binding returns an empty tuple; `src/aeat/domain/calculations/registry/_bindings.py` and `src/aeat/domain/calculations/registry/test_formula_runtime.py`.
- [x] `P01.S05` - run the cross-dependency contract and calculation suites and the formula-runtime suite to confirm no regression; `src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`, `src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`, `src/aeat/domain/calculations/registry/test_formula_runtime.py`.

### Phase `P02` - pre-flip bound-casilla sweep audit

Enumerate every bound casilla across the registry, resolve each through its current binding, and write the audit catalogue. This Phase produces no code change.

- [x] `P02.S06` - implement a one-off audit script that loads every modelo revision via `load_registry_tree`, enumerates every casilla with `input_kind = "bound"`, resolves the named binding from the same revision, classifies the result as one of {resolves_with_anchors, declared_anchors_no_observation_path, no_anchors_no_relation_dead, relation_driven_with_relation, relation_driven_orphaned}, and writes a JSON inventory; `the script lives under `.vault-scratch/` as a one-off; the resulting JSON is checked into the vault as an audit artefact and the script is discarded`.
- [x] `P02.S07` - persist the audit catalogue at `.vault/audit/2026-05-26-bound-casilla-binding-resolution-sweep-audit.md` via `vault add audit`; `the body lists every (modelo, revision, casilla_id, binding_id, classification) tuple in a markdown table with provenance to the source TOML`.
- [x] `P02.S08` - for every binding classified as `no_anchors_no_relation_dead` or `relation_driven_orphaned`, either repair the binding using the Phase `P01` `max_year_delta` capability if the binding declares same-ejercicio quarterly carry-forward semantics, or revise the binding/casilla declaration so the runtime flip in Phase `P03` will not surface it as a calculation error; `each repair lands as its own commit against the affected modelo TOML`.

### Phase `P03` - runtime flip and provenance

Eliminate the silent zero default. Bound casillas resolve exclusively through the binding pipeline; absent-by-design bindings materialise zero through an explicit constructor.

- [x] `P03.S09` - extend `_initial_values` to reject `inputs` targeting any casilla with `input_kind = "bound"`, raising `RegistryValidationError` ("bound registry casillas cannot be supplied as inputs: {ids!r}") parallel to the existing computed-casilla rejection; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `P03.S10` - extend `_initial_values` to source bound casilla values from the resolved `binding_values` mapping rather than from `inputs`; `a bound casilla whose binding declared no anchors for the target period is materialised via an explicit `Decimal("0")` constructor that carries an absent-by-design provenance marker on the resulting `CasillaObservation`; a bound casilla whose binding declared anchors but did not deliver a value raises `RegistryValidationError`; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `P03.S11` - add an `absent_by_design: bool = False` field (or equivalent provenance marker — name finalised at implementation against the existing `CasillaObservation` model) to `CasillaObservation` with strict pydantic config; `the materialiser in `_materialise_observations` sets the flag for absent-by-design zeros, leaves it `False` for resolved values; `src/aeat/domain/calculations/registry/_bindings.py`.
- [ ] `P03.S12` - sweep all calculation-runtime tests and fixtures that pass bound casillas through `inputs` (e.g. the `"15": Decimal("0")` shape in the M130 formula-runtime tests); `rewrite each to route the bound value through the `binding_values` pipeline or remove the input entry if the binding's anchors are absent-by-design for that target period; tests across `src/aeat/domain/calculations/registry/test_formula_runtime.py` and any sibling suites surfaced by the run`.
- [ ] `P03.S13` - run the calculation, formula-runtime, cross-dependency, and modelo-suite tests to confirm the runtime flip is clean; `the run is expected to surface any bound-casilla input fixtures missed in S12 — fix each surfaced fixture in this Step rather than deferring`.

### Phase `P04` - Modelo 130 binding revision and legal grounding

Revise the carry-forward binding against the new selector capability and strengthen the legal grounding.

- [ ] `P04.S14` - revise the `modelo-130-resultados-negativos-anteriores` binding selector to declare `source_period_offset_from_target = -1` and `max_year_delta = 0`; `the binding's TOML comment is updated to document the same-ejercicio first-period-suppression contract; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [ ] `P04.S15` - extend `[legal."rd-439-2007:art-110"].required_text` in `src/aeat/_data/registry/aeat/legal/irpf.toml` with the art. 110.5 BOE-verbatim carry-forward sentence fragment; `if the corpus normative source at `corpus/normatives/rd-439-2007.json#art-110` does not carry the fragment, re-fetch the corpus document and update its content before extending `required_text`.
- [ ] `P04.S16` - run the registry validation suite to confirm the legal-text-fragment check passes against the revised `required_text` and the binding selector validates against the new `_PreviousModeloSelector` shape; `src/aeat/domain/calculations/registry/test_registry_schema.py`, `src/aeat/domain/calculations/registry/test_referential_integrity.py`, and the cross-dependency contract suite`.

### Phase `P05` - regression test suite

Three real-behaviour tests gate the regression against future revival.

- [ ] `P05.S17` - add `test_modelo_130_first_period_carry_forward_is_absent_by_design`: build a 1T M130 snapshot, calculate with no previous-filing observations, assert C15 = `Decimal("0")` AND assert the materialised `CasillaObservation` for C15 carries the absent-by-design provenance marker; `the test must fail today against the pre-flip runtime (silent-zero indistinguishable from absent-by-design) and pass against the post-flip runtime; `src/aeat/domain/calculations/registry/test_modelo_130_registry.py`.
- [ ] `P05.S18` - add `test_modelo_130_second_period_carry_forward_picks_up_first_period_saldo`: construct a 1T `RegistryModeloObservation` with casilla 17 negative so the seed `saldo-negativo-fin-periodo` is positive, resolve previous-filing bindings against a 2T snapshot via `resolve_previous_filing_binding_values`, pass the resolved value into `calculate_registry_snapshot`'s `binding_values` for the 2T calculation, assert C15 equals the 1T saldo seed, assert C17 reflects the subtraction, assert the C15 `CasillaObservation` carries provenance pointing at the 1T source (modelo, year, period); `src/aeat/domain/calculations/registry/test_modelo_130_registry.py`.
- [ ] `P05.S19` - add `test_modelo_130_bound_casilla_rejects_input_override`: call `calculate_registry_snapshot` against a 2T snapshot with `inputs={"15": Decimal("100")}`; `assert `RegistryValidationError` is raised, the message names casilla 15, and the error references the `input_kind = "bound"` rejection reason; `src/aeat/domain/calculations/registry/test_modelo_130_registry.py`.
- [ ] `P05.S20` - run the M130 registry suite, the formula-runtime suite, the cross-dependency contract and calculation suites, and the full registry test directory to confirm no regression across the campaign; `src/aeat/domain/calculations/registry/`.
