---
tags:
  - '#reference'
  - '#linkage-design-audit'
date: '2026-05-15'
modified: '2026-05-15'
related: []
---



# `linkage-design-audit` reference: Linkage Defect Taxonomy v1

This document defines the canonical defect-class taxonomy derived from the
102-row raw inventory and the Tier 1/2/3 convergent findings (F1–F21) in the
companion research record. Each class names a structurally distinct failure
mode in how types, schemas, validators, and boundaries are wired across the
AEAT codebase. The taxonomy is the primary input for writing mechanical checks.

Audit posture: LLM-driven agents are the discovery layer; mechanical checks
(registry validators, structural tests, lint rules, import-linter rules) are
the verification layer. Coverage is measured as `mechanical_checks / surface_elements`,
not as `agents_run`. All numerators below are zero at time of writing.

---

## Defect classes

### T-01. Untyped string-keyed cross-boundary value envelope

**Description.** A cross-boundary data structure uses `Mapping[str, Decimal]`
or `dict[str, str]` as its value container where a typed pydantic model carrying
`casilla_id: CasillaId`, `value: Decimal`, and provenance fields is required.
The string key is a casilla identifier with no compile-time or load-time
enforcement of the `CasillaId` constraint. Downstream consumers must re-parse
the key or silently accept garbage.

**Signature.** Pydantic-model field whose annotation matches
`Mapping[str, Decimal]` or `dict[str, str | Decimal]` where the model is a
cross-boundary observation or revision type (identified by appearing in
`_bindings.py`, `_relations.py`, `_formula_runtime.py`, or
`_calculation_revision.py`). AST form: `AnnAssign` whose annotation is a
`Subscript` with `slice` containing `str` as first element and `Decimal` or
`str` as second.

**Surface.** Every pydantic field on `RegistryFilingObservation`,
`RegistryCalculationResult`, `CalculationRevision`, `RegistryRelationSourceRequirement`,
`ExportFieldDefinition`, and `WorkbookParityReference` under `src/aeat/`. The
surface is enumerable mechanically by inspecting `model_fields` on all pydantic
models in the package.

**Coverage.** 0 / 11 confirmed inventory sites. Broader surface — 116
`Mapping[str, ...]` field declarations across `src/aeat/domain/` per the
surface enumeration — narrows to ~25 cross-boundary value envelopes
once filtered to observation, result, and revision types.

**Inventory rows.** R001, R002, R003, R004, R005, R006, R013, R014, R089, R092, R096.

**Example.** R002 — `src/aeat/domain/calculations/registry/_bindings.py:66-90`:
`RegistryFilingObservation.casilla_values: Mapping[str, Decimal]`. Any string
is accepted as a casilla key; the `CasillaId` pattern constraint (`^[A-Za-z0-9][A-Za-z0-9._:-]*$`)
is never enforced at the point of construction.

**Promotion path.** Adopt the typed observation envelope pattern (analogous
to OpenFisca's `Population.get_holder(variable).get_array(period)` returning
a typed array bound to a `Variable` and `Period`). Mechanical
implementation: a `libcst` one-shot codemod rewrites `Mapping[str, Decimal]`
field declarations and construction sites to a typed
`CasillaObservation` model; a `semgrep` pattern rule
(`pattern: $X: Mapping[str, Decimal]` scoped to registry models) prevents
regression. Confirmed in the prior-art research as items 1, 5, and 6 of the
recommended adoption order.

---

### T-02. Untyped selector sub-schema

**Description.** A pydantic field holds a `Mapping[str, str | int | ...]` that
acts as one of ten or more mutually exclusive sub-schemas discriminated at
runtime by a sibling `source` literal field. The correct sub-schema is
validated only when a binding handler calls `model_validate(dict(binding.selector))`
at invocation time, not at registry load. Any structural error in the selector
is invisible until that handler executes.

**Signature.** Pydantic-model field annotated `Mapping[str, str | int | ...]`
on a model that also has a `source: Literal[...]` or `kind: Literal[...]` field.
Python `ast` pattern: `AnnAssign` on a class that has another field annotated
with `Literal`.

**Surface.** `DataBindingDefinition.selector`, `RelationDefinition.source_revision_selector`,
and `RelationDefinition.period_alignment` in `src/aeat/domain/calculations/registry/_schema.py`.
All downstream raw-dict accesses (`selector.get("year")`, `selector.get("source_modelo")`)
in `_relations.py` and `_validate.py`. Surface is enumerable by searching for
`.get(` calls on fields annotated `Mapping`.

**Coverage.** 0 / 3 confirmed selector fields. Surface enumeration confirms
only 5 explicit discriminated unions exist across `src/aeat/` against 195
`Literal[...]` declarations — promotion ceiling is high.

**Inventory rows.** R007, R008, R009, R010, R015, R016.

**Example.** R007 — `src/aeat/domain/calculations/registry/_schema.py:817`:
`DataBindingDefinition.selector: Mapping[str, str | int | ...]`. The `source`
field on the same model takes values such as `"ledger"`, `"invoice"`,
`"rental"`, each requiring a different selector shape. Validation is deferred
to the handler (see R010).

**Promotion path.** Adopt pydantic v2 discriminated unions via
`Field(discriminator='source')` over a `Union` of narrow per-source pydantic
models. This is item 1 of the prior-art adoption order — confirmed
in-session against the pydantic v2 documentation. Enforces the correct
selector shape at `ModeloRevision.model_validate(payload)` time, eliminating
all raw `.get()` call sites; mypy/pyright flag missing match arms in
consumers as a side benefit.

---

### T-03. Deferred or absent cross-domain validation

**Description.** A referential integrity check exists in the codebase but is
guarded by an explicit call to `validate_registry` or `validate_modelo`, making
it conditional on user or test action rather than automatic at snapshot construction.
Some checks are entirely absent despite the referenced field being declared on
the schema. The registry loads successfully with broken cross-references.

**Signature.** A `_validate_*` function that is called only inside
`validate_registry` or `validate_modelo` (grep: `def _validate_` not reachable
from `__init__` or snapshot constructor). Also: pydantic model fields with an
ID type where no `_missing_refs` call exists in any validator path (grep:
`CasillaId | str` fields without a corresponding `_missing_refs` reference).

**Surface.** All existence checks in `src/aeat/domain/calculations/registry/_validate.py`
and any field declared as an ID type on a schema model. The surface is enumerable
by cross-referencing the 21 ID types in `_ids.py` against the call graph of
`_validate.py`.

**Coverage.** 0 / 21 ID types confirmed mechanically (surface enumeration:
21 in `_ids.py`, all `Annotated[str, Field(pattern=...)]`, none currently
with existence checks at snapshot construction). Wider validator surface:
411 `ConfigDict` instances of which 51 lack `extra="forbid"` — a separate
T-03 sub-class.

**Inventory rows.** R010, R015, R016, R017, R018, R019, R036, R037, R038, R048,
R049, R053, R071, R091, R100.

**Example.** R019 — `src/aeat/domain/calculations/registry/_schema.py:831`:
`CasillaDefinition.validation_refs` is a tuple of `LegalRefId` values but no
`_missing_refs` call exists for this field in any validation path. A
`CasillaDefinition` referencing a non-existent legal ref loads silently.

**Promotion path.** Adopt pydantic `@model_validator(mode="after")` on the
`RegistrySnapshot` constructor (item 1 of prior-art adoption). Complement
with `taplo check --schema` against pydantic-exported JSON Schemas (item 4)
to catch dangling references at the TOML source layer before Python
execution. Add a `validate_registry` invocation to `aeat config repair` so
the operator-facing surface (F2) gains observability. This promotion path
ties directly to Alexis King's "Parse, Don't Validate" principle cited in
Part E of the prior-art research.

---

### T-04. Same-semantic-concept multiple shapes (type proliferation)

**Description.** A single domain concept (casilla schema, casilla ID in a
cross-modelo reference, CCAA code, sensitivity classification attachment point)
is represented by two or more structurally incompatible types in different
packages. Consumers must perform ad-hoc conversion or accept type degradation.
This is the pydantic-model-consistency audit target.

**Signature.** Two or more pydantic models or dataclasses in different packages
that share a name segment (e.g., `*CasillaSchema*`, `*CasillaId*`, `*CCAA*`)
but differ in their field types or annotations for the same semantic field.
Also: `isinstance(x, str)` discrimination on a field that should be a typed
union. AST: `Compare` with `isinstance` where the right operand is `str`.

**Surface.** All pydantic models and protocols under `src/aeat/` that carry
casilla, modelo, period, CCAA, or sensitivity-classification fields. Enumerable
via `model_fields` introspection and name-pattern search.

**Coverage.** 0 / 16 confirmed shape pairs from inventory. Surface ceiling:
580 `BaseModel` subclasses across `src/aeat/` (280 domain / 150 application
/ 100 adapters) — the universe within which name-pattern consolidation must
be detected and resolved.

**Inventory rows.** R014, R022, R023, R024, R029, R030, R031, R039, R040, R042,
R054, R094, R095, R098, R099, R102.

**Example.** R024 — Three coexisting shapes for "casilla schema":
`CasillaDefinition` in `src/aeat/domain/calculations/registry/_schema.py:882`
(pydantic, strict, typed IDs, `Decimal` bounds), `RegistryCasillaSchema` in
`src/aeat/application/filing/runtime.py:78` (frozen dataclass, `str` IDs,
`float | int | None` bounds), `CasillaSchema` in
`src/aeat/domain/filing/_protocols.py:38` (structural Protocol, no legal refs).

**Promotion path.** Adopt `CasillaDefinition` as the single canonical shape;
remove competing types via `libcst` codemod (prior-art item 5). Add an
`import-linter` `forbidden` contract (item 3) preventing direct construction
of deprecated shapes outside the migration boundary. A `semgrep` rule (item
2) flags any future declaration of a model whose name matches an existing
canonical concept (`*CasillaSchema*`, `*CCAA*`). Each consolidation is a
one-time rewrite; the rules prevent regression.

---

### T-05. Hard-coded constants outside the registry

**Description.** A mapping from a domain concept (spending category, binding
kind, modelo identifier) to a casilla ID or set of casilla IDs is declared as
a module-level Python constant rather than as a TOML-declared registry field.
The registry TOML and the Python constant can diverge silently; no load-time
cross-check enforces agreement.

**Signature.** Module-level `Mapping[..., str]` or `dict[..., str]` where the
values are strings matching the `CasillaId` pattern (`^\d{4}$` or
`^[A-Za-z0-9][A-Za-z0-9._:-]*$`) and the mapping is consumed in a binding
handler or validator that is not connected to registry load. Grep: top-level
`= {` or `= Mapping` assignments in `domain/renta/` or `domain/calculations/`.

**Surface.** `src/aeat/domain/renta/_ledger_expenses.py` and any file under
`domain/calculations/registry/` that declares module-level casilla-ID constants.
Surface is small and enumerable by direct inspection.

**Coverage.** 0 / 4 confirmed constant sites in inventory (the 4th is
`_export.py:_ROW_FIELD_CASILLA_BY_RECORD`). Surface is small and fully
enumerated.

**Inventory rows.** R025, R026, R027, R090.

**Example.** R025 — `src/aeat/domain/renta/_ledger_expenses.py:27`:
`RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS: Mapping[SpendingCategory, str]`
hard-codes casilla IDs `"0186"`, `"0192"`, `"0199"`, `"0203"`. The registry
TOML owns the authoritative `CasillaDefinition` for these same IDs but the
Python constant has no load-time assertion that the IDs still exist in the
snapshot.

**Promotion path.** Move the mapping into the registry TOML as a
`category_casilla_mapping` field on `DataBindingDefinition.selector`. Once
the discriminated-union selector (T-02 promotion) lands, this field becomes
typed automatically. A `semgrep` rule (prior-art item 2) flags any future
module-level `Mapping[..., str]` constant whose values match the
`CasillaId` pattern, preventing regression.

---

### T-06. Architecture-boundary violation

**Description.** A module in one domain package imports a private symbol from
a sibling domain package, crossing the hexagonal boundary in the wrong direction.
The canonical dependency direction is domain → (no cross-domain imports);
adapters and application layers mediate. A cross-domain import in the registry
package creates a coupling the architecture rules forbid.

**Signature.** An import statement in any file under `domain/calculations/`
that references `domain/renta/` or vice versa (or any other cross-domain pair).
Import-linter contract rule: `source_modules = domain.calculations.*`,
`forbidden_modules = domain.renta.*`.

**Surface.** All cross-domain import edges in `src/aeat/domain/`. Enumerable
mechanically by `import-linter` or `pydeps`.

**Coverage.** 0 / 1 confirmed cross-domain violation. Surface enumeration:
424 cross-package imports across `src/aeat/domain/` total — the broader
surface for a `layers` contract once the hexagonal direction is encoded.

**Inventory rows.** R028.

**Example.** R028 — `src/aeat/domain/calculations/registry/_bindings.py:12`
imports from `src/aeat/domain/renta/`. This is the sole confirmed cross-domain
import in the registry layer. The renta-specific logic it pulls in should be
mediated through the application layer or expressed as registry configuration.

**Promotion path.** Adopt `import-linter` (prior-art item 3, confirmed
actively maintained at v2.9). Start with a `forbidden` contract for
`domain.calculations` → `domain.renta` to close R028, then expand to a
`layers` contract encoding the hexagonal direction. `tach` was evaluated
but flagged as unmaintained after mid-2025 and is not recommended. The
single call site in `_bindings.py:12` must be resolved by moving the
dependency into an application-layer provider.

---

### T-07. CLI and operator output erasure

**Description.** A typed, semantically rich object (formula trace entries
carrying `legal_refs`, `source_refs`, `operand_refs`; validation finding
`source` field; workflow step details) is stripped or dropped before it
reaches the operator-facing CLI output or JSON payload. The operator receives
a degraded or opaque representation with no path back to the typed original.

**Signature.** A `_emit_*` function or CLI command handler that constructs an
output `dict` by discarding fields present on the input domain object. Also:
`engine_result.entries` assigned to `_` or not referenced after the calculation
call. AST: `Assign` of `dict(engine_result.values)` without a parallel
assignment of `engine_result.entries`.

**Surface.** All `_emit_*` and `_calculation_revision_payload` functions in
`src/aeat/entrypoints/cli/`. All sites where `RegistryCalculationResult` or
`FilingValidationFinding` is consumed in the CLI or application layer.

**Coverage.** 0 / 11 confirmed CLI emit sites. Surface ceiling: 153 CLI
commands across `src/aeat/entrypoints/` per surface enumeration, of which
zero use `SchemaEnvelope` / `emit_json_success` today (F9 confirmed).

**Inventory rows.** R001, R006, R023, R044, R045, R046, R047, R074, R075, R094, R097.

**Example.** R001 — `src/aeat/application/modelo/_actions.py:817`:
`dict(engine_result.values)` is persisted into `CalculationRevision.casilla_values`
while `engine_result.entries` (the full formula trace carrying legal refs,
source refs, operand refs, and operand values) is silently discarded. This is
the primary drop site for downstream linkage erasure.

**Promotion path.** Persist `engine_result.entries` inside
`CalculationRevision` (the canonical drop site R001). Apply the existing
unused `SchemaEnvelope` / `emit_json_success` infrastructure (see T-08).
Adopt OpenFisca's `reference: list[LegalRef]` per-formula convention
(prior-art item 6) so legal grounding survives every emission. A `semgrep`
rule (item 2) flags any `_emit_*` that constructs a payload without
including all known typed-ID fields from the source object. A structural
pytest asserts `CalculationRevision` round-trips through the CLI without
dropping `legal_refs`.

---

### T-08. Unused typed JSON contract (documentation-implementation drift)

**Description.** A typed JSON envelope contract (`SchemaEnvelope`, `emit_json_success`,
`register_schema`) is implemented and documented but has zero call sites in
production code. CLI command handlers emit ad-hoc `dict` payloads that bypass
the contract. Some CLI flags or options are documented in docstrings but absent
from the actual argument parser.

**Signature.** A symbol that is defined in a `core/` or `application/` module
and appears in zero `import` statements in `entrypoints/cli/` (importable but
unused). Also: a CLI docstring containing `--<flag>` that has no corresponding
`parser.add_argument` or `typer.Option` in the same file.

**Surface.** `src/aeat/core/json_contract.py` (`SchemaEnvelope`, `emit_json_success`,
`register_schema`) and all `_emit_*` sites in the CLI entrypoint. Also
`src/aeat/entrypoints/cli/_config/_google.py` docstrings vs argument definitions.

**Coverage.** 0 / 6 confirmed inventory rows. Surface enumeration: zero
imports of `SchemaEnvelope`, `emit_json_success`, or `register_schema`
across the 153-command CLI surface.

**Inventory rows.** R043, R044, R049, R050, R051, R052.

**Example.** R043 — `src/aeat/core/json_contract.py:75,167,259-274`:
`SchemaEnvelope`, `emit_json_success`, and `register_schema` are fully
implemented. A grep across `entrypoints/cli/` finds zero imports of any of
these symbols. All CLI commands emit raw `dict` payloads instead.

**Promotion path.** Adopt `emit_json_success` in every `_emit_*` function.
A `semgrep` rule (prior-art item 2) flags any new CLI command that emits a
raw `dict` payload bypassing the envelope. A structural pytest imports
every public symbol from `core/json_contract.py` and asserts it has at
least one non-test caller (this same pattern catches the absent
`--prefill-relations` flag — docstring-vs-arg-parser drift, R052). CLI
integration tests assert each model work-lifecycle command's JSON output
conforms to the `SchemaEnvelope` schema.

---

### T-09. Missing existence check for typed ID reference

**Description.** A field on a pydantic model is annotated with a typed ID
alias (e.g., `CasillaId`, `OracleId`, `WorkbookParityRefId`) or with
`CasillaId | str`, but no validator confirms that the referenced entity exists
in the registry snapshot at load time. The type annotation signals intent but
provides no enforcement.

**Signature.** A pydantic model field annotated with any of the 21 ID types
declared in `_ids.py`, or with `SomeId | str`, where no `_missing_refs` call
or `@field_validator` checks existence in the snapshot. Import-graph predicate:
field type references `_ids.py` symbol but owning class has no validator
referencing the registry.

**Surface.** All 21 ID types in `src/aeat/domain/calculations/registry/_ids.py`
cross-referenced against all model fields that use them. Enumerable via pydantic
`model_fields` introspection combined with call-graph analysis of validators.

**Coverage.** 0 / 21 mechanically confirmed (every ID type in `_ids.py`).
Per the surface enumeration: 20 of 21 ID types have pattern validation
only, with no existence check anywhere in the validator path.

**Inventory rows.** R011, R012, R019, R020, R021, R073, R089, R092, R101.

**Example.** R021 — `src/aeat/domain/calculations/registry/_ids.py:14-34`:
All 21 ID types are `Annotated[str, Field(pattern=...)]`. The pattern constraint
validates the format of the string but no check confirms the referenced entity
(formula, binding, relation, legal ref, etc.) exists in the snapshot. R011 is
a specific instance: `RelationDefinition.source_output: CasillaId | str` where
the `str` fallback eliminates even the format guarantee.

**Promotion path.** Implement `_check_all_id_references` as a pydantic
`@model_validator(mode="after")` on `RegistrySnapshot` (prior-art item 1).
For each ID type, declare a mapping from ID type to the registry
collection that owns it; the validator walks all fields of all registered
models and asserts existence. This closes all 21 ID types with one
implementation and is the single highest-leverage promotion in the entire
taxonomy (closes T-09 and most of T-03 simultaneously — see the promotion
plan below).

---

### T-10. Hard-wired per-modelo gate

**Description.** A code path checks for a specific modelo identifier (e.g.,
`"100"`) as a string literal to gate logic that should be driven by registry
configuration. Adding a new modelo requires modifying application or adapter
code rather than only adding a TOML declaration.

**Signature.** A string literal `"100"` or `"303"` etc. compared with `==` or
used as a default value in a field annotation, in a file outside the registry
TOML files and outside `_ids.py`. Grep: `== "100"` or `default="100"` in
`src/aeat/application/` or `src/aeat/adapters/`.

**Surface.** `src/aeat/application/modelo/_borrador_binding.py`,
`src/aeat/application/aggregation/_renta_ledger.py`, and
`src/aeat/domain/justificante/_repository.py`. Surface is small and enumerable
by grep.

**Coverage.** 0 / 4 confirmed gate sites (the SensitivityClass hardcoding
counts as a per-domain gate). Surface enumeration: 1005 modelo number
string literals exist in `src/aeat/`, of which only 3 are confirmed
hard-wired application-level gates (most are in test or data files); the
gate-detection rule must filter accordingly.

**Inventory rows.** R034, R035, R037, R038.

**Example.** R034 — `src/aeat/application/modelo/_borrador_binding.py:27,79,98,179`:
`_MODELO_100 = "100"` is a permanent exclusive gate. The borrador binding
applies only to modelo 100 through hard-coded equality checks rather than
through a registry-declared capability flag on the `ModeloDefinition`.

**Promotion path.** Add a `capabilities: set[Literal["borrador", ...]]`
field to `ModeloDefinition`. Replace each `_MODELO_100` equality check with
`"borrador" in snapshot.modelo(modelo_id).capabilities`. A `semgrep` rule
(prior-art item 2) flags new `== "100"` comparisons and
`default="100"`-style field defaults outside registry TOML files. The same
pattern applies to sensitivity-classification gates — schema-attach
`output_sensitivity` on `ModeloDefinition` and detect hard-coded enum
assignments in repositories.

---

### T-11. Type-system escape

**Description.** A `cast(...)`, `# type: ignore`, or `dict[str, Any]`
annotation is used to bridge a type boundary where a proper pydantic model
or typed adapter should be used instead. These sites disable mypy/pyright
enforcement and allow structural errors to pass undetected.

**Signature.** Any of: `cast(Any, ...)`, `cast(SomeType, unrelated_value)`,
`# type: ignore[...]` (any code), `dict[str, Any]` as a field type on a
pydantic model, `Mapping[str, Any]` on a cross-boundary value. Grep:
`# type: ignore` in `src/aeat/`; `dict\[str, Any\]` in pydantic model files.

**Surface.** All Python files under `src/aeat/`. The surface is large;
priority is `domain/`, `application/`, and `adapters/outbound/`. Enumerable
by `ruff` or `grep`.

**Coverage.** 0 / 28 confirmed inventory rows. Surface enumeration totals:
100 `cast(...)` calls, 85 `# type: ignore` comments (of which 32 are
forced-mutation, 9 are `__iter__` overrides, 6 are `computed_field`), 33
files with `dict[str, Any]`, and 50 files with `Mapping[str, Any]` — a
combined raw surface of ~268 sites once enumerated at file:line resolution.

**Inventory rows.** R056, R057, R058, R059, R060, R061, R062, R063, R064,
R065, R066, R067, R068, R069, R070, R072, R074, R076, R077, R078, R079,
R080, R081, R082, R083, R084, R085, R086.

**Example.** R056 — `src/aeat/domain/calculations/registry/_loader.py:73,77,167,172`:
`model_validate` is called over a raw `dict[str, Any]` produced by
`tomllib.loads()`. The `Any`-typed dict bypasses mypy enforcement between
the TOML parse and the pydantic boundary. A typed intermediate representation
for TOML payloads would catch structural mismatches before `model_validate`.

**Promotion path.** Enable `ruff` rule `ANN401` (disallow `Any` in
annotations) scoped to `src/aeat/domain/` and `src/aeat/application/`.
Note from the prior-art research: `ruff` has no plugin system yet, so
class-specific signatures beyond stock rules require `semgrep` (prior-art
item 2). For `adapters/`, replace `dict[str, Any]` API response bodies
with pydantic models or `TypedDict` schemas validated at the adapter
boundary. A `libcst` codemod (item 5) can mechanically rewrite the
`cast(...)` and trivial `# type: ignore` sites once a typed replacement
exists.

---

### T-12. Hand-authored data with no schema coupling

**Description.** A data structure (BOE record spec, parity scenario, sidecar
TOML, Google Sheets cell reference) is authored manually from an external
document (BOE PDF, workbook) and stored in Python or TOML without a structural
test that confirms it is consistent with the registry schema or the source
document. Errors introduced by manual transcription are invisible until runtime.

**Signature.** A module-level tuple or list of tuples whose elements are
positional (not named) and whose values are hard-coded integers or strings
referencing byte offsets, cell addresses, or field names from an external
authoritative document. Also: a `ParityScenario` or `SheetCellAddress`
construction with hand-typed string values.

**Surface.** `src/aeat/adapters/outbound/aeat/export/_formats/` (all
`_RECORD_SPECS` modules), `src/aeat/application/storage/calc_sheets/_parity_tapes.py`,
and `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`. Enumerable by
file.

**Coverage.** 0 / 8 confirmed inventory rows touching hand-authored data.
Per-modelo `_RECORD_SPECS` modules are the primary subset; the workbook
parity tapes and Google Sheets pull magic-key extraction sites complete
the surface.

**Inventory rows.** R032, R033, R065, R066, R087, R088, R090, R093.

**Example.** R088 — `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`
and per-modelo siblings: `_RECORD_SPECS` tuples are transcribed from BOE PDFs.
There is no structural test asserting that the total declared byte length
matches the BOE-specified record length, or that every casilla ID named in a
spec entry exists in the registry snapshot for the corresponding modelo revision.

**Promotion path.** Add a parametrised pytest that, for each `_RECORD_SPECS`
module, loads the corresponding registry snapshot and asserts (a) total
byte length matches the BOE-declared record size, (b) every named casilla
ID exists in the snapshot. For the workbook parity scenario surface, the
same test pattern asserts every declared `WorkbookCellRef` resolves to a
casilla-bearing cell. The OpenFisca `reference: list[LegalRef]` pattern
(prior-art item 6) provides a complementary primitive: every BOE record
spec entry should carry its own `reference` field so transcription drift
between BOE PDF and code is detected by inspection.

---

## Coverage summary

Denominators are grounded in the surface enumeration appended to the
companion research record. Two numbers are reported per class: `confirmed
inventory rows / total mechanical surface`. The confirmed-inventory column
is the number of distinct file:line sites already named in the audit;
the total-surface column is the upper bound the mechanical check would
range over once written.

| Class | Description (short) | Surface (broader denominator) | Inventory rows covered | Mechanical surface coverage | Recommended tool | Highest-impact row |
|-------|---------------------|-------------------------------|------------------------|-----------------------------|------------------|--------------------|
| T-01 | Untyped string-keyed value envelope | 116 `Mapping[str, ...]` fields in `src/aeat/domain/` | 0 / 11 | 0 / ~25 cross-boundary subset | libcst codemod + pydantic typed envelope + semgrep regression rule | R001 |
| T-02 | Untyped selector sub-schema | 5 explicit discriminated unions vs 195 `Literal[...]` declarations | 0 / 6 | 0 / 3 selector fields | pydantic `Field(discriminator=...)` | R007 |
| T-03 | Deferred or absent validation | 21 ID types in `_ids.py`; 51 pydantic models without `extra="forbid"` | 0 / 15 | 0 / 21 (ID types) plus 0 / 51 (extra-forbid gaps) | pydantic `model_validator(mode="after")` + taplo TOML schema | R017 |
| T-04 | Same-concept multiple shapes | 580 `BaseModel` subclasses | 0 / 16 | 0 / ~30 estimated name-pattern pairs | import-linter + libcst codemod + semgrep | R024 |
| T-05 | Hard-coded constants outside registry | Module-level mappings in `domain/renta/` and `domain/calculations/registry/_export.py` | 0 / 4 | 0 / 4 (fully enumerated) | TOML migration + semgrep | R025 |
| T-06 | Architecture-boundary violation | 424 cross-package imports under `src/aeat/domain/` | 0 / 1 | 0 / 1 confirmed; layers contract over full surface | import-linter | R028 |
| T-07 | CLI / operator output erasure | 153 CLI commands in `src/aeat/entrypoints/` | 0 / 11 | 0 / ~25 emit sites | SchemaEnvelope adoption + OpenFisca `reference` pattern + semgrep | R001 |
| T-08 | Unused typed JSON contract | 0 of 3 `json_contract.py` symbols imported by CLI | 0 / 6 | 0 / 3 unused symbols | adopt `emit_json_success` + structural caller-count test | R043 |
| T-09 | Missing existence check for typed ID | 21 ID types in `_ids.py` | 0 / 9 | 0 / 21 (one per ID type) | pydantic `model_validator` + `_check_all_id_references` | R021 |
| T-10 | Hard-wired per-modelo gate | 1005 modelo-number string literals (most in data/tests); 3 confirmed application gates | 0 / 4 | 0 / 3 application-level gates | `ModeloDefinition.capabilities` field + semgrep | R034 |
| T-11 | Type-system escape | 100 `cast()` + 85 `# type: ignore` + 33 files with `dict[str, Any]` + 50 files with `Mapping[str, Any]` ≈ 268 raw sites | 0 / 28 | 0 / 268 raw surface | ruff `ANN401` + semgrep + libcst codemod | R056 |
| T-12 | Hand-authored data without schema coupling | Per-modelo `_RECORD_SPECS` modules + parity tapes + Sheets magic keys | 0 / 8 | 0 / 8 | parametrised pytest + OpenFisca `reference: list[LegalRef]` per spec entry | R088 |

Reading: T-09's coverage `0 / 21` is the most actionable single denominator
in the taxonomy — every one of 21 ID types is currently unchecked, every
one closes with one validator function, and T-09 plus T-03's existence-
check subset are closed by the same implementation.

---

## Promotion plan

Ordered by leverage (rows closed per mechanical check). Tool recommendations
are sourced from the prior-art research and have been confirmed in-session
against authoritative documentation.

- **T-09 + T-03 together (closes ~42 rows with one implementation).**
  Implement `_check_all_id_references` as a pydantic
  `@model_validator(mode="after")` on the `RegistrySnapshot` constructor.
  Walks all 21 ID types, confirms every reference points to an existing
  entity, fires at every registry load. Subsumes most of T-03's
  deferred-validation gap and all of T-09's missing-existence gap.
  Tooling: pydantic v2 model validators (prior-art item 1). This is the
  highest-leverage single change in the entire taxonomy. Complementary:
  `taplo check --schema` (item 4) catches the same dangling references at
  the TOML source layer before Python execution.

- **T-01 (closes ~11 inventory rows; structurally repairs the canonical
  drop site).** Persist `engine_result.entries` in `CalculationRevision`
  (R001). Replace `Mapping[str, Decimal]` on the three primary
  cross-boundary models with a typed `CasillaObservation` envelope.
  Tooling: `libcst` codemod (item 5) for the one-shot migration; `semgrep`
  rule (item 2) for regression detection. The OpenFisca pattern (item 6)
  is the conceptual reference for typed value envelopes carrying period
  and variable provenance.

- **T-11 (closes ~28 inventory rows, ~268 raw escapes incrementally).**
  Enable `ruff ANN401` scoped to `src/aeat/domain/` and
  `src/aeat/application/`. Each violation is a failing lint check. For
  pattern signatures beyond stock ruff rules, use `semgrep` (item 2 — ruff
  has no plugin system per the prior-art research). Address violations in
  dependency order: domain first, then application, then adapters.

- **T-02 (closes 6 rows; eliminates an entire class of raw `.get()` calls).**
  Introduce discriminated-union selectors for `DataBindingDefinition` and
  `RelationDefinition` via pydantic `Field(discriminator='source')` (item
  1). This replaces every raw-dict `.get()` call site wholesale and makes
  the existing `model_validate`-at-load path enforce correctness.

- **T-07 (closes ~11 rows).** Apply `SchemaEnvelope` / `emit_json_success`
  to all CLI emit sites (resolves T-08 simultaneously). Adopt OpenFisca's
  `reference: list[LegalRef]` per-formula convention (item 6) so legal
  grounding survives every emission. One `semgrep` rule (item 2) flags
  any `_emit_*` that drops typed-ID fields. One structural pytest asserts
  `CalculationRevision` round-trips through the CLI without losing
  `legal_refs`.

- **T-04 (closes ~16 inventory rows by consolidation).** Adopt
  `CasillaDefinition` as the canonical casilla schema and delete
  `RegistryCasillaSchema`. Collapse the three CCAA enums to one. Tooling:
  `libcst` codemod (item 5) for the rewrite; `import-linter` (item 3)
  with `forbidden` contracts prevents reintroduction of competing shapes;
  `semgrep` (item 2) flags new name-pattern duplicates.

- **T-12 (closes 8 rows).** Add a parametrised pytest covering all
  per-modelo `_RECORD_SPECS` modules plus the parity scenario catalogue.
  Adopt OpenFisca's `reference: list[LegalRef]` per spec entry (item 6)
  so transcription drift between BOE PDFs and code becomes detectable by
  inspection.

- **T-06 (closes 1 confirmed row; prevents recurrence across full
  boundary surface).** Add an `import-linter` (item 3) `forbidden`
  contract for `domain.calculations` → `domain.renta`. Expand to a
  `layers` contract encoding the hexagonal direction once the immediate
  violation is resolved. `tach` was evaluated as a candidate but flagged
  unmaintained after mid-2025 and is not recommended.

- **T-05 (closes 4 rows).** Move `RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS`
  and similar constants into the registry TOML as binding selector
  fields. After T-02's discriminated-union selectors land, these fields
  are validated at load with no Python-side constants required. A
  `semgrep` rule (item 2) flags any new module-level
  `Mapping[..., str]` whose values look like `CasillaId`.

- **T-08 (closes 6 rows).** Adopt `emit_json_success` in every `_emit_*`
  function. Add a structural pytest that imports every public symbol
  from `core/json_contract.py` and asserts it has at least one non-test
  caller. Same pattern catches docstring-vs-arg-parser drift (R052: the
  missing `--prefill-relations` flag).

- **T-10 (closes 4 rows; prevents regression).** Add a
  `capabilities: set[Literal[...]]` field on `ModeloDefinition`.
  Replace each hard-wired equality check with a capability lookup.
  Schema-attach `output_sensitivity: SensitivityClass` on
  `ModeloDefinition` and `CasillaDefinition`. A `semgrep` rule (item 2)
  flags new `== "100"` comparisons and `default="100"` field values
  outside registry TOML.

### Tool inventory and assignment

| Tool / pattern | Prior-art rank | Closes classes | Status |
|----------------|----------------|----------------|--------|
| pydantic discriminated unions + `model_validator(mode="after")` | 1 | T-02, T-03, T-09 | not adopted |
| `semgrep` taxonomy rules | 2 | T-01, T-04, T-05, T-07, T-08, T-10, T-11 (regression detection) | not adopted |
| `import-linter` forbidden + layers contracts | 3 | T-04, T-06 | not adopted |
| `taplo check --schema` | 4 | T-03 (TOML-layer) | not adopted |
| `libcst` codemod | 5 | T-01, T-04, T-11 (one-shot migrations) | not adopted |
| OpenFisca `reference` + period-parameterised formula pattern | 6 | T-01, T-07, T-12 | not adopted |
| `ruff ANN401` (built-in) | n/a | T-11 (stock subset) | not adopted |
| Structural pytest patterns (round-trip, caller-count) | n/a | T-07, T-08, T-12 | not adopted |
| `tach` | — | (declined; unmaintained after mid-2025) | not adopted |

The tool inventory makes adoption decisions explicit. The "Status" column
becomes the operational tracker once an ADR commits to a subset.

---

## Post-execution closure update

This appendix updates the coverage table earlier in this document
with the verdict of a scripted re-audit (`scratch/reaudit_inventory.py`)
that re-walked **all 102 inventory rows** against current code.
The earlier "98 / 102 closed (96%)" claim was extrapolated from
inventory edits rather than verified.

**Verified closure: 48 / 102 (47%)**. Real numbers across all
rows:

| verdict           | count | share |
|-------------------|------:|------:|
| verified          |    48 |   47% |
| regressed         |    30 |   29% |
| partial           |    16 |   16% |
| open              |     2 |    2% |
| wontfix-confirmed |     4 |    4% |
| unverified        |     2 |    2% |

Numerators in the per-class table below reflect verified
structural delivery only; partials are not counted.

| Class | Verified closures (re-audit sample) | Notes |
|-------|--------------------------------------|-------|
| T-01 | partial — `CasillaObservation` typed envelope verified on `RegistryFilingObservation` (`R002`). Selector typing across `DataBindingDefinition` / `RelationDefinition` / `period_alignment` (`R007`, `R008`, `R009`) regressed: fields are still bare `Mapping[str, ...]`. The semgrep regression rule exists; the structural rewrite did not land. |
| T-02 | regressed — discriminated `BindingSelector` `Union` does not exist in `_schema.py`. Selector fields remain bare `Mapping[str, ...]`. |
| T-03 | partial — `AlgorithmBindingDefinition` targets typed (`R012` verified); `_check_all_id_references` exists and is tested (`R021` partial) but **not wired into `build_snapshot`** — runs only in tests, never at runtime. |
| T-04 | partial — typed-envelope migrations on observation models verified; selector unions absent (see T-02). |
| T-05 | partial — `_MODELO_100` gate removed and replaced with capability lookup (`R034` verified); `_renta_ledger.modelo` default removed (`R035` verified); but `RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS` constant in `_ledger_expenses.py` is still present (`R025` regressed). |
| T-06 | partial — registry→renta import inverted (`R028` verified); two of the four `import-linter` contracts are kept (`no-renta-in-registry`, `core-not-outer`); the `layered` and `domain-not-application` contracts remain broken. |
| T-07 | partial — `SchemaEnvelope` adopted at 20+ `register_schema` sites in CLI (`R043` verified); no raw-dict `_emit` sites remain in `_modelo.py` (`R044` verified); but `formulas` command body does not surface `legal_refs` / `--explain` (`R046` partial). |
| T-08 | verified — `_modelo_payloads.py` declares 15+ typed payload classes wired to CLI emit sites. |
| T-09 | **not delivered as a runtime gate** — the validator function is defined in `_validate.py` and tested, but is **not invoked by `build_snapshot`**. Production builds do not run the gate; only the dedicated tests do. |
| T-10 | partial — `_borrador_binding` migrated to capability lookup (`R034` verified); the renta ledger default migrated (`R035` verified). |
| T-11 | not re-verified — the suppression-inventory dashboard still reports 175 total ty:ignores (76 internal); no claim can be made about removed sites without per-site tracking. |
| T-12 | partial — M303 `form_number` declared (`R098` verified); M100 2025 `export_refs` present (`R032` verified); `_RECORD_SPECS` modules are still hand-authored without `legal_refs` declarations (`R088` open, as inventory recorded). |

### Defect classes whose closure narrative is wrong as written

The earlier write-up of this appendix overstated coverage on:

- **Selector discriminated unions (T-01 / T-02).** No discriminated
  `Union` over selector sub-shapes exists in `_schema.py`. The
  selector remains structurally untyped at the schema boundary.
- **Snapshot referential-integrity gate (T-03 / T-09).** The
  validator is implemented; the wiring into `build_snapshot` is
  not. Snapshots constructed in production do not currently run the
  21-typed-ID existence check.
- **Workflow-step typed details (operator surface).** `WorkflowStep.details`
  is still `dict[str, str] | None`. The `WorkflowStepDetails`
  discriminated `Union` claimed in this document does not exist in
  `application/workflow/_models.py`.
- **FilingDraft identity propagation.** `subject_tax_id` was claimed
  added; the field present is `profile_tax_id: str` (bare `str`).
  No typed `TaxId` / `SubjectTaxId` participates in `FilingDraft`,
  and `schema_version: str` was not replaced with a
  `RegistrySnapshotRef`.
- **Oracle typing.** `LiveCrossReferenceDecision.oracle_id` is still
  `str | None`; `OracleFilingObservation` subtype does not exist in
  `_bindings.py`.
- **CLI `--relation` flag on `work calculate`.** Absent from the
  `work_calculate` command. The application-layer plumbing
  (`relation_values` kwarg) is present (`R051`); the CLI surface
  is not. The flag is present on `aeat config export` only.
- **`_load_snapshot` error handling on Google export.** The
  `RegistrySnapshotError` symbol is not imported by
  `_config/_google.py`. The exception, if raised, is not caught.

The unified `scratch/linkage_health.py` dashboard remains the right
mechanical-coverage tracker. It should be re-run before any future
claim of closure.
