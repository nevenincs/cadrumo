---
tags:
  - '#plan'
  - '#linkage-design-audit'
date: '2026-05-17'
tier: L2
related:
  - '[[2026-05-15-linkage-design-audit-research]]'
  - '[[2026-05-15-linkage-design-audit-reference]]'
  - '[[2026-05-16-linkage-design-audit-audit]]'
  - '[[2026-05-16-linkage-design-audit-plan]]'
  - '[[2026-05-26-linkage-design-audit-research]]'
  - '[[2026-05-26-linkage-design-audit-adr]]'
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

# `linkage-design-audit` `Wave 3: referential integrity and typed envelope (Phase 3 of linkage epic)` plan

### Phase `P01` - referential integrity gate at registry load

Implement `_check_all_id_references` as a pydantic `model_validator`
on `RegistrySnapshot`. Walks the 21 typed IDs declared in `_ids.py`
and asserts existence in the snapshot at every registry load. Closes
T-09 (0 / 21 coverage) and most of T-03 in one implementation. The
single highest-leverage change in the entire taxonomy.

- [x] `P01.S01` - declare ID-to-collection mapping and the validator function — verified already-satisfied: `_validate.py` carries the `RegistryValidator` class plus the cross-domain `_validate_references.py:_check_all_id_references` companion; together they own the ID-to-collection mapping and the per-snapshot validation entrypoint; `src/aeat/domain/calculations/registry/_validate.py`.
- [x] `P01.S02` - wire validator into RegistrySnapshot constructor — verified already-satisfied: `_snapshot.py` imports `RegistryValidator` (line 12) and `_check_all_id_references` (line 13), installs cross-domain snapshot checks idempotently, and runs them at snapshot build; `src/aeat/domain/calculations/registry/_snapshot.py`.
- [x] `P01.S03` - add `aeat config repair` cross-domain integrity diagnostic — verified already-satisfied: `application/diagnostics.py:252` defines `build_config_repair_report` + `render_config_repair_text` (line 449); the CLI `_config/__init__.py` imports them (wired into the `aeat config repair` surface); `src/aeat/application/diagnostics.py`.
- [x] `P01.S04` - add structural pytest exercising the validator against the committed registry — verified already-satisfied: `test_referential_integrity.py` carries 49 tests exercising the referential-integrity validator against the committed registry; 49 green in this session's run; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.

### Phase `P02` - typed cross-boundary value envelope

Define `CasillaObservation` model carrying `(casilla_id, value,
formula_id, legal_refs, source_refs, source_modelo, source_period,
source_filing_year)`. Replace `Mapping[str, Decimal]` on the three
primary cross-boundary models. Persist `engine_result.entries` in
`CalculationRevision` (the canonical R001 drop site). Migrate via
libcst codemod.

- [x] `P02.S05` - define CasillaObservation typed envelope; `src/aeat/domain/calculations/registry/_bindings.py`.
- [ ] `P02.S06` - persist engine_result.entries in CalculationRevision; `src/aeat/application/modelo/_actions.py`.
- [x] `P02.S07` - replace casilla_values on RegistryFilingObservation; verified already-satisfied: the class is now `RegistryModeloObservation` and stores `observations: tuple[CasillaObservation, ...]` canonically with `casilla_values` as a derived `@property` at lines 117-127 (R002 verified by the close-out audit); `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `P02.S08` - replace values on RegistryCalculationResult; landed: `observations: tuple[CasillaObservation, ...]` is now canonical storage, `values` and `entries` are derived `@property` views, `CasillaObservation` extended with `op: str | None` so the entry projection round-trips losslessly; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `P02.S09` - replace casilla_values on CalculationRevision; landed stage one per ADR `2026-05-26-linkage-design-audit-adr`: `_outputs_for_hash_from_mapping` + `_outputs_for_hash_from_observations` helpers carry the canonical `{casilla_id: canonical_decimal_str}` projection; `derive_calculation_revision_id` routes through `_outputs_for_hash_from_mapping` for byte-stable hash; `CalculationRevision._enforce_invariants` re-projects `observations` and asserts equality with the persisted `casilla_values` (raises `ModeloValidationError` on drift, tolerates empty observations on historical revisions). Hash-stability pin (P08.S35) stays green; 10/10 unit tests green; 16/16 across 3 roundtrip suites green; stage two (drop the flat field, JSON-schema migration) deferred to a future ADR per the staged path; `src/aeat/domain/modelos/_calculation_revision.py`.
- [x] `P02.S10` - migrate downstream consumers via libcst codemod; superseded by the ADR `2026-05-26-linkage-design-audit-adr` staged path — stage one (P02.S09 landing) preserves the `casilla_values=` constructor kwarg unchanged, so the 27 construction sites need no codemod migration today. The codemod work resurfaces inside the future stage-two ADR (`casilla-values-flat-field-retirement`) when the actual field signature changes to a derived `@property`; tracked there, not at this surface; `src/aeat/`.
- [x] `P02.S11` - add semgrep rule preventing Mapping[str, Decimal] regression on registry-tier models; verified already-satisfied: `.semgrep/rules/no-mapping-str-decimal-on-registry.yml` declares `no-mapping-str-decimal-on-registry-models` covering all three registry-tier model files with `Mapping[str, Decimal]` / `dict[str, Decimal]` / `Dict[str, Decimal]` pattern variants.

### Phase `P03` - discriminated selector unions

Replace `DataBindingDefinition.selector: Mapping[str, str|int|...]`
with a discriminated Union of per-source pydantic models, keyed by
the sibling `source: Literal` field. Eliminates raw `.get()` call
sites across the binding handlers.

- [x] `P03.S12` - declare per-source selector models; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P03.S13` - convert DataBindingDefinition.selector to discriminated union; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P03.S14` - update binding handlers to consume typed selectors; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `P03.S15` - eliminate raw selector.get() call sites in validators; `src/aeat/domain/calculations/registry/_validate.py`.

### Phase `P04` - hexagonal-direction enforcement

Resolve the three import-linter contracts deferred in Wave 2 P06.
Each requires refactor of an offending production path before its
contract can be activated.

- [x] `P04.S16` - refactor domain.deadlines._profiles to remove application.wizard import; `src/aeat/domain/deadlines/_profiles.py`.
- [x] `P04.S17` - refactor domain.profile._keys to remove application.wizard import; `src/aeat/domain/profile/_keys.py`.
- [x] `P04.S18` - refactor core.errors to remove adapters.outbound import; `src/aeat/core/errors/__init__.py`.
- [x] `P04.S19` - refactor core.i18n._render to remove application imports; `src/aeat/core/i18n/_render.py`.
- [x] `P04.S20` - refactor domain.attachments._repository to remove adapters import; `src/aeat/domain/attachments/_repository.py`.
- [x] `P04.S21` - activate domain-not-application import-linter contract; `.importlinter`.
- [x] `P04.S22` - activate core-not-outer import-linter contract; `.importlinter`.
- [x] `P04.S23` - activate full layered import-linter contract; `.importlinter`.

### Phase `P05` - CLI legal-grounding surfacing

Adopt the existing `SchemaEnvelope` infrastructure at CLI emit
sites. Add the `--explain` flag per the existing ADR convention so
the operator-facing surface prints `legal_refs` / `source_refs`
attached at the registry layer.

- [ ] `P05.S24` - apply emit_json_success to modelo work-lifecycle commands; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `P05.S25` - add typed context keys to RegistryValidationError; landed per ADR `2026-05-26-linkage-design-audit-adr` decision 2 (`registry-error-typed-context-factories`) — 18 classmethod factories on `RegistryValidationError` (`for_unsupported_op`, `for_unknown_parameter`, `for_dispatch_key_unknown`, `for_lookup_dispatch_arg_kind`, `for_lookup_dispatch_arg_count`, `for_dispatch_parameter_kind`, `for_enum_binding_value_missing`, `for_binding_value_missing`, `for_relation_value_missing`, `for_casilla_referenced_before_evaluation`, `for_unknown_input_casillas`, `for_computed_supplied_as_input`, `for_bracket_no_window`, `for_bracket_no_coverage`, `for_bracket_negative_base`, `for_divide_by_zero`, `for_empty_expression`, `for_unsupported_comparison_op`) covering every canonical raise scenario the frequency-ranked inventory surfaced. Each pins its context-dict keys and `translated_message` identifier. 20/20 contract tests at `test_error_factories.py`. Existing constructor signature stays valid; raise-site migration is additive; `src/aeat/domain/calculations/registry/_errors.py`.
- [x] `P05.S26` - add typed context keys to RegistrySnapshotError; landed in the same commit — single canonical `for_modelo_not_registered(modelo_id=)` factory covering the `_authority.modelo` boundary's sole raise scenario; bare constructor stays valid for one-off subscenarios not yet promoted; `src/aeat/domain/calculations/registry/_errors.py`.
- [ ] `P05.S27` - implement --explain flag printing legal_refs in modelo formulas; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P05.S28` - surface legal_refs in review queue findings; `src/aeat/entrypoints/cli/_review.py`.

### Phase `P06` - hand-authored data structural coverage

Address T-12 from the taxonomy. BOE record specs in
`_RECORD_SPECS` tuples per modelo are hand-authored from BOE PDFs.
Parametrised pytest asserts byte-length and casilla-id integrity
against the registry snapshot. Adopt OpenFisca's `reference:
list[LegalRef]` per spec entry.

- [x] `P06.S29` - add parametrised pytest for record-spec byte-length integrity; `src/aeat/adapters/outbound/aeat/export/_formats/test_record_specs.py`.
- [x] `P06.S30` - add parametrised pytest for record-spec casilla-id resolution; `src/aeat/adapters/outbound/aeat/export/_formats/test_record_specs.py`.
- [x] `P06.S31` - add reference field to RecordFieldSpec naming the source BOE Orden; `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`.

### Phase `P07` - close-out audit

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `P07.S32` - re-run linkage health dashboard and capture final state; `scratch/out/linkage_health.json`.
- [x] `P07.S33` - regenerate feature index; landed via `uv run vaultspec-core vault feature index --feature linkage-design-audit`; `.vault/index/linkage-design-audit.index.md`.
- [x] `P07.S34` - write Wave 3 close-out audit; landed at `.vault/audit/2026-05-26-linkage-design-audit-audit.md` recording the P02 typed-envelope-collapse closure (R002/R003/R004/R005), supporting W09 hygiene gates, M303 migration, the staged-path ADR ratification, recommendations for the stage-two ADR + Wave 3 P05 follow-on; `.vault/audit/`.

### Phase `P08` - CalculationRevision typed-envelope close-out (hash-stability pre-flight)

Surfaced during P02.S08 (RegistryCalculationResult collapse, commit
`6963600c0`). P02.S09 and P02.S10 remain the highest-risk rows of
the linkage epic because `derive_calculation_revision_id` is
SHA-256 content-addressed and currently feeds on
`casilla_values: Mapping[str, Decimal]`. Collapsing the field
without preserving the hash function's domain breaks every
already-persisted CalculationRevision. This Phase stages the
pre-flight so S09 lands cleanly.

- [x] `P08.S35` - write the hash-stability anti-tautology proof BEFORE touching the field: landed as `test_revision_id_pinned_against_fully_populated_fixture` — pins SHA-256 `5b78dd04e614a50fe448439b7fdb843f1e31afe76f9d424d0276866679dee7ca` for a fully-populated derivation exercising every branch of the hash payload (inputs, overrides, outputs, source_transaction_ids, borrador_snapshot_id, bindings_sourced_from_borrador). Any future change to the hash domain — including the planned S09 collapse of `casilla_values` into a derived projection — must keep this pin stable, or every already-persisted CalculationRevision id phantom-mismatches. 7/7 tests in the file green; `src/aeat/domain/modelos/test_calculation_revision.py`.
- [x] `P08.S36` - decide the hash-domain projection: either (a) keep the flat `{casilla_id: Decimal}` shape but build it from `observations` at hash time, or (b) define a new canonical projection over `observations` and bump the revision-id derivation contract with a documented migration; decided: **staged two-strategy path** ratified at `2026-05-26-linkage-design-audit-adr` (status: accepted). Stage one lands an `_outputs_for_hash(observations)` helper routing both the model validator and `derive_calculation_revision_id` through the projection; `casilla_values` becomes a denormalised cache enforced equal at construction time. Hash domain unchanged — pinned SHA stable. Stage two (drop the flat field, JSON-schema migration) is deferred to a separate ADR after one release cycle. Research note `2026-05-26-linkage-design-audit-research` carries the cross-campaign-collision survey, the two-strategy tradeoff table, and the recommendation; `.vault/adr/2026-05-26-linkage-design-audit-adr.md`.
- [x] `P08.S37` - execute P02.S09 against the pre-flight pin: per the ADR's staged path, the wave-one landing keeps `casilla_values` as a model field (not @property) but enforces it equal to `_outputs_for_hash_from_observations(observations)` at construction. Hash derivation routes through `_outputs_for_hash_from_mapping`; both helpers produce the same canonical projection so the P08.S35 pin (`5b78dd04…`) resolves identically. Stage two (true @property) deferred to a separate ADR after one release cycle; `src/aeat/domain/modelos/_calculation_revision.py`.
- [x] `P08.S38` - execute P02.S10 codemod against the 27 construction sites only after S37 lands; the codemod is mechanical once the storage shape stabilises; superseded by the ADR staged path — stage one keeps the constructor kwarg shape, so no codemod is required today. Resurfaces inside the future stage-two ADR `casilla-values-flat-field-retirement`; `src/aeat/`.
- [x] `P08.S39` - run the four persistence roundtrip suites (`test_calculation_repository_roundtrip.py`, `test_secure_storage_roundtrip.py`, `test_cross_boundary_roundtrip.py`, `test_runtime_migrated_repositories.py`) and confirm every fully-populated fixture survives strict pydantic equality across the boundary; 16/16 across the first three suites green after S37 landing; `test_runtime_migrated_repositories.py` deferred — that suite collects against the in-flight `live-iva-compensation-wallet` backend (`RepairRemediationDecision` et al.) tracked at W09.P20.S143, not at this surface; will re-verify once the upstream campaign lands; `src/aeat/`.
