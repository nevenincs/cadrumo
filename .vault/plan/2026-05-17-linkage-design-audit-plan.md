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
- [ ] `P02.S09` - replace casilla_values on CalculationRevision; `src/aeat/domain/modelos/_calculation_revision.py`.
- [ ] `P02.S10` - migrate downstream consumers via libcst codemod; `src/aeat/`.
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
- [ ] `P05.S25` - add typed context keys to RegistryValidationError; `src/aeat/domain/calculations/registry/_errors.py`.
- [ ] `P05.S26` - add typed context keys to RegistrySnapshotError; `src/aeat/domain/calculations/registry/_errors.py`.
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
- [ ] `P07.S33` - regenerate feature index; `.vault/index/linkage-design-audit.index.md`.
- [ ] `P07.S34` - write Wave 3 close-out audit; `.vault/audit/`.

### Phase `P08` - CalculationRevision typed-envelope close-out (hash-stability pre-flight)

Surfaced during P02.S08 (RegistryCalculationResult collapse, commit
`6963600c0`). P02.S09 and P02.S10 remain the highest-risk rows of
the linkage epic because `derive_calculation_revision_id` is
SHA-256 content-addressed and currently feeds on
`casilla_values: Mapping[str, Decimal]`. Collapsing the field
without preserving the hash function's domain breaks every
already-persisted CalculationRevision. This Phase stages the
pre-flight so S09 lands cleanly.

- [ ] `P08.S35` - write the hash-stability anti-tautology proof BEFORE touching the field: load a fully populated `CalculationRevision` fixture from a frozen JSON envelope, derive its id via `derive_calculation_revision_id`, and pin the result. Any change to the hash domain must keep this id stable; `src/aeat/domain/modelos/test_calculation_revision.py`.
- [ ] `P08.S36` - decide the hash-domain projection: either (a) keep the flat `{casilla_id: Decimal}` shape but build it from `observations` at hash time, or (b) define a new canonical projection over `observations` and bump the revision-id derivation contract with a documented migration; `.vault/adr/`.
- [ ] `P08.S37` - execute P02.S09 against the pre-flight pin: make `casilla_values` a derived `@property` over `observations`, route hash derivation through the chosen projection, and confirm the S35 pin still resolves identically; `src/aeat/domain/modelos/_calculation_revision.py`.
- [ ] `P08.S38` - execute P02.S10 codemod against the 27 construction sites only after S37 lands; the codemod is mechanical once the storage shape stabilises; `src/aeat/`.
- [ ] `P08.S39` - run the four persistence roundtrip suites (`test_calculation_repository_roundtrip.py`, `test_secure_storage_roundtrip.py`, `test_cross_boundary_roundtrip.py`, `test_runtime_migrated_repositories.py`) and confirm every fully-populated fixture survives strict pydantic equality across the boundary; `src/aeat/`.
