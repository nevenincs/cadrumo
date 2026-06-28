---
tags:
  - '#reference'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-13-google-oauth-calc-sheets-adr]]"
  - "[[2026-05-13-google-oauth-twoway-adr]]"
  - "[[2026-05-13-google-oauth-plan]]"
---

# `google-oauth` reference: `calc engine + modelo schema reference`

Audit of the registry-backed calculation engine and the modelo TOML schema
surface, prepared for the schema-to-Sheets engine that mirrors registry
formulas onto a Google Sheets document with bit-exact recomputation.

## Findings

The calculation surface is a strict, validated, declarative graph: TOML
registry files (`registry/aeat/modelos/*.toml` plus the directory-layout
`modelos/100/`) declare casillas, parameters, bindings, relations, and
formula expressions; pydantic v2 models in
`src/aeat/domain/calculations/registry/_schema.py` lock the schema;
`_loader.py` walks the tree with a TOML fingerprint LRU cache;
`_formula_runtime.calculate_registry_snapshot` is the single entry point
that evaluates every declared formula in topological order and returns
the casilla map. A `CalculationRevision` pydantic record (under
`aeat.domain.modelos._calculation_revision`) content-addresses the
result for the work-unit lifecycle. There is no existing Sheets-writer
surface; the only `googleapiclient` import in the tree is the Drive v3
binary-blob provider at
`src/aeat/adapters/outbound/storage/_google_drive.py:123`. ADR
`2026-05-13-google-oauth-calc-sheets-adr` reserves the `calc-sheets`
namespace under `/aeat-vault/_workspace/`.

### 1. Modelo schema surface — corpus and shape

24 modelo files live under `registry/aeat/modelos/`. 23 are single-file
TOML at modelo-id top level; Modelo 100 is the only directory-layout
modelo, segmented into six per-revision files (2020-2025). The split
is enforced by the loader at `_loader.py:178-248` (the same modelo
cannot appear in both single-file and directory layouts).

Full enumeration of `registry/aeat/modelos/`:

`100/manifest.toml` + `100/revisions/{2020,2021,2022,2023,2024,2025}.toml`,
`111.toml`, `115.toml`, `123.toml`, `130.toml`, `131.toml`,
`180.toml`, `184.toml`, `190.toml`, `193.toml`,
`200.toml`, `202.toml`, `232.toml`,
`303.toml`, `308.toml`, `309.toml`, `322.toml`,
`347.toml`, `349.toml`, `353.toml`, `360.toml`, `369.toml`,
`390.toml`, `720.toml`, `840.toml`.

Modelo 100's 2025 revision is the largest single TOML in the registry
at 25,353 lines; `130.toml` is 1,485 lines; `303.toml` is 589 lines.
Op-token density (grep `op = ` per file): `100/2025=2491`, `131=390`,
`232=440`, `180=78`, `130=32`, `111=32`, `303=9`, `184=6`, `840=2`.
Most modelos declare a single revision; Modelo 100 has six.

Top-level shape of every modelo file is the same. Excerpt from
`130.toml:1-16` shows the canonical header:

`[modelo]` table — id, title, official_name, tax_domain (`irpf` / `iva`
/ `iae`), cadence (`monthly`/`quarterly`/`annual`/`ad_hoc`/`profile_based`),
jurisdiction (always `ES-AEAT`), legal_refs, source_refs.

`[revisions."<revision_id>"]` table — one per regulatory revision
window, with `label`, `valid_from`, optional `valid_to`,
`period_selector = { year_from = 2019, periods = ["1T", "2T", "3T", "4T"] }`,
legal_refs, source_refs.

Inside each revision, repeated array-of-tables members:
`[[revisions."<id>".parameters]]`, `[[revisions."<id>".casillas]]`,
`[[revisions."<id>".formulas]]`, `[[revisions."<id>".bindings]]`,
`[[revisions."<id>".relations]]`,
`[[revisions."<id>".algorithm_providers]]`,
`[[revisions."<id>".algorithm_bindings]]`,
`[[revisions."<id>".extraction_profiles]]`,
`[[revisions."<id>".live_cross_references]]`,
`[[revisions."<id>".workbook_parity_refs]]`,
`[[revisions."<id>".verification_expectations]]`,
`[[revisions."<id>".application_links]]`,
`[[revisions."<id>".deadline_windows]]`,
`[[revisions."<id>".filing_schedules]]`,
`[[revisions."<id>".support_removal_decisions]]`,
`[[revisions."<id>".constructs]]`,
`[[revisions."<id>".dependency_classifications]]`.

#### 1.1 Vocabulary (taken from the TOML)

- **Casilla** — one numbered cell on the AEAT form. Carries `id`,
  `number`, `label`, `section`, `data_type` (one of
  `decimal money integer ratio text boolean`), `required`, and
  `input_kind` (one of `manual bound computed informational`). A manual
  casilla is operator input; a bound casilla pulls its value from a
  `binding`; a computed casilla is the output target of a `formula`;
  informational is metadata (e.g. `decl.ejercicio` on Modelo 303).
  Pydantic guard at `_schema.py:865-875` enforces that
  `input_kind = "computed"` requires `formula =` and forbids `binding`,
  while `input_kind = "bound"` requires `binding =` and forbids
  `formula`.

- **Formula** — `id`, `target` (the casilla id it writes), `expression`
  (a recursive `FormulaExpression`), `rounding` (`money-2` / `integer`
  / `none`), legal_refs, source_refs. See `_schema.py:840-847`. Modelo
  130 example: `[[revisions."2019-y-siguientes".formulas]]` at
  `130.toml:288-294` declares `modelo-130-rendimiento-neto` writing
  casilla 03 as
  `{ op = "subtract", args = [{ casilla = "01" }, { casilla = "02" }] }`.

- **FormulaExpression** — the recursive op tree. Pydantic record at
  `_schema.py:692-724`. Either an operator (`op` + non-empty `args`) or
  a leaf carrying exactly one of: `casilla`, `binding`, `parameter`,
  `relation`, `literal`, or `dispatch_table`. The leaf-vs-operator
  validator enforces the XOR constraint.

- **Binding** — `id`, `source` kind (one of `ledger`,
  `ledger_transaction`, `ledger_iva_aggregation`,
  `ledger_oss_aggregation`, `ledger_renta_expense_aggregation`,
  `rental`, `vat`, `category`, `profile`, `previous_filing`,
  `manual_input`, `purchase_invoice_evidence`, `payable_invoice`,
  `collectible_invoice`), a typed `selector`, an optional
  `aggregation`, `aeat_prefilled` flag, and optional `typed_enum`
  discriminator. The runtime resolves bindings upstream of
  `calculate_registry_snapshot`, passing in the resulting Decimal map
  as `binding_values=`. See `_schema.py:813-837`. Example: Modelo 303
  `modelo-303-iva-repercutido-general-cuota` at `303.toml:61-67`
  selects `category=domestic_general_21`, `rate_kind=general`,
  `flow_direction=repercutido`, `fact=iva_amount_sum`, aggregation
  `op = "sum"`.

- **Parameter** — a versioned numeric value or piecewise-linear bracket
  schedule. `_schema.py:772-810`. Two shapes:
    1. Dated values (`values = [...]` of `DatedValue`) for scalar
       parameters like
       `irpf.direct_estimation_fractional_payment_rate = 20`
       (`130.toml:18-32`). Each value carries `date_axis`, `valid_from`,
       optional `valid_to`.
    2. Bracket tables (`brackets = [...]` of `BracketEntry`) for
       piecewise-linear escalas, e.g. IRPF state and autonomic rate
       scales. Each entry has `lower_bound`, optional `upper_bound`,
       `fixed_addition`, `marginal_rate`, `valid_from`, optional
       `valid_to`. Pydantic enforces non-overlapping ranges and a
       single bracket axis. Used by ops `lookup_bracket` /
       `lookup_bracket_by_ccaa`.

- **Relation** — cross-modelo / cross-period dependency.
  `_schema.py:902-936`. Three kinds: `previous_period`,
  `annual_summary`, `cross_model_output`. Encodes the source modelo,
  source revision selector, source output casilla, source periods,
  target periods, target binding id, and period_alignment. The
  relation's resolved Decimal flows into
  `calculate_registry_snapshot(..., relation_values=...)`. Modelo 200's
  `modelo-200-2024-rel-202-pagos-fraccionados` (`200.toml:95-105`) is a
  canonical cross-modelo relation: `source_modelo=202`,
  `source_output=34`, `source_periods=["1P", "2P", "3P"]`,
  `target_periods=["0A"]`,
  `dependency_role=instalment_to_final_settlement`.

- **Oracle** (vocabulary used loosely across the registry) maps to two
  distinct surfaces. (a) `LiveCrossReferenceDecision` entries with
  `oracle_id` — runtime AEAT verification adapters registered in
  `LiveParityCatalogue` for synthetic-payload verification (e.g.
  `aeat-nif-iva` checker, GROI driver, `renta-web-open` simulator).
  (b) `WorkbookParityReference` entries — the AEAT-published `dr.xls`
  workbook bound to the registry for executable parity verification.
  `_schema.py:298-437` and `_schema.py:440-463`.

- **Construct** — a grouping that names which casillas, formulas,
  parameters, bindings, relations, layouts, etc. collectively
  materialise one logical filing surface. The Modelo 303 quarterly
  autoliquidacion construct (`303.toml:521-589`) lists 10 casillas, 3
  formulas, 5 bindings, the workbook parity ref, both live
  cross-references, every application link, and every deadline window.
  `_schema.py:536-607`.

#### 1.2 Three representative modelos

**Modelo 130 (simple quarterly IRPF pago fraccionado).** `130.toml`,
1485 lines, one revision `2019-y-siguientes`. 19 casillas (01-19)
organised in 4 sections: actividades directas, actividades agrarias,
total liquidacion, resultado final. 13 are `input_kind = "manual"`, 6
are `input_kind = "computed"`. 11 formulas. Two parameters
(direct-estimation 20% rate, agrarian 2% rate). One binding:
`irpf.previous_year_economic_activity_net_income` —
`source = "previous_filing"`. The expression vocabulary used:
`subtract`, `add`, `percent`, `max`, plus `previous_period_value` on
Modelo 130's `modelo-130-minoracion-rendimientos-netos` formula that
consumes the previous-filing binding.

**Modelo 303 (mid-complexity quarterly IVA).** `303.toml`, 589 lines,
one revision `2009-y-siguientes`. 10 casillas: 5 `bound` (the five IVA
aggregation buckets), 3 `computed`, 2 `informational`. The bound
casillas pull from `ledger_iva_aggregation` bindings; the computed
casillas implement `cuota devengada = sum of 4 repercutido buckets`,
`cuota deducible = soportado + autorepercutido`,
`resultado regimen general = devengada - deducible`. Includes Modelo
390 cross-modelo dependency target (the three computed casillas feed
Modelo 390 annual summary). One workbook_parity_ref
(`modelo-303-dr-2025` against `aeat-dr-303-2025`).

**Modelo 100 (complex annual IRPF declaracion).**
`100/manifest.toml` + six per-year revision files. 2025 revision is
25353 lines containing 2491 op-tokens. The revision declares hundreds
of casillas (manual, bound, computed), parameters with bracket tables
for state-scale and each of the 15 ordinary common-regime autonomous
communities, and the only registry instance of the
`lookup_bracket_by_ccaa` op for CCAA-dispatched escala autonomica
computation. Carries cross-modelo relations against Modelos
111/115/123/130/131 for periodic to annual aggregation of retentions
and instalment payments. The 2025 revision validates against the
`aeat-renta-2025-manual-parte1` and
`aeat-renta-2025-manual-deducciones-autonomicas` corpus manuals plus
the `aeat-renta-web-open` live parity oracle.

#### 1.3 Formula DSL — op corpus

Every op the schema permits is whitelisted by the
`FormulaOperator = Literal[...]` type at `_schema.py:62-86`.
Twenty-two distinct ops appear across the committed registry. Observed
frequencies (grep `op = "..."` across all modelo TOMLs):

- `sum` (657 occurrences) — n-ary addition
- `negate` (623) — unary sign flip
- `subtract` (328) — 2-arg
- `percent` (106) — `arg[0] * arg[1] / 100`
- `copy` (101) — 1-arg passthrough (typical for binding/relation
  read-throughs)
- `max` (94)
- `min` (62)
- `equals` (62) — TOML alias of schema's `equal` comparator
- `add` (58) — 2+ arg (alias of `sum` in practice)
- `if_then_else` (34) — 3-arg: returns `args[1]` when `args[0]` is
  non-zero, else `args[2]`
- `rows` (24) — appears only in `relations.aggregation` blocks, not
  in formula expressions (out-of-band)
- `multiply` (24)
- `greater_than` (24)
- `divide` (24)
- `lookup_bracket` (12) — state-scale bracket lookup
- `lookup_bracket_by_ccaa` (12) — CCAA-dispatched bracket lookup, all
  in `100/revisions/`
- `equal` (6)
- `less_equal` (4)
- `count_distinct` (2) — only in aggregation blocks
- `not_equals` (1) — only in profile predicate blocks

The runtime's `_evaluate_expression` at `_formula_runtime.py:152-309`
implements: `add`, `sum`, `subtract`, `multiply`, `divide`, `percent`,
four comparators (`less_than`, `less_equal`, `greater_than`,
`greater_equal`, `equal`), `min`, `max`, `clamp`, `negate`, `copy`,
`lookup_parameter`, `lookup_bracket`, `lookup_bracket_by_ccaa`,
`previous_period_value`, `previous_period_sum`, `cross_model_sum`,
`if_then_else`. Comparator results return `1` for true and `0` for
false (Decimal). `clamp` is 3-arg
(`max(args[1], min(args[0], args[2]))`).

Rounding rules are restricted to three literals
(`_formula_runtime.py:420-427`): `money-2` (1065 occurrences, quantize
`0.01` HALF_UP), `integer` (5 occurrences), `none` (6 occurrences, no
rounding). Decimal context is `prec=28` inside `localcontext()` at
`_formula_runtime.py:91-92`.

#### 1.4 Cross-period, cross-modelo, autonomic-scale

Cross-modelo / cross-period state surfaces through three distinct
mechanisms:

- **Relations** with `kind = "cross_model_output"` — authoritative
  cross-modelo wiring. 11 occurrences. Example: `200.toml:95-105`
  resolves Modelo 200's annual settlement binding from three Modelo 202
  quarterly outputs; `100/revisions/2025.toml:8122-8132` aggregates
  four Modelo 111 quarterly retentions into Modelo 100's annual
  binding. Runtime resolution:
  `_relations.resolve_relation_values_from_observations`, re-exported
  by the package as
  `aeat.domain.calculations.registry.resolve_relation_values_from_observations`.

- **Relations** with `kind = "previous_period"` and
  `kind = "annual_summary"` — temporal carryforwards (e.g. Modelos
  180/190/193 annual summaries of quarterly 111/115/123). Files
  declaring these: `200.toml`, `190.toml`, `193.toml`, `180.toml`,
  `100/revisions/2025.toml`.

- **Bindings** with `source = "previous_filing"` — the registry's
  binding-resolved channel for read-back from previously filed
  declarations. Example Modelo 130's
  `modelo-130-rendimientos-netos-trimestres-anteriores` binding.
  Runtime resolution: `resolve_previous_filing_binding_values`
  (`registry/__init__.py:21`).

- **Bindings** with `source = "ledger_renta_expense_aggregation"`,
  `"ledger_iva_aggregation"`, `"ledger_oss_aggregation"` —
  bucket-derived aggregations from the local ledger. The values are
  computed externally (per the per-modelo aggregation pipeline) and
  passed in as `binding_values`.

**Autonomic-scale chains.** The Modelo 100 IRPF computation selects a
different progressive-rate bracket table per taxpayer CCAA. The DSL
surfaces this through `op = "lookup_bracket_by_ccaa"`, which carries
three args: the base amount (a casilla), an enum binding leaf carrying
the CCAA key
(`{ binding = "renta-2025-profile-tax-residence-ccaa" }`), and a
`dispatch_table` leaf mapping CCAA keys to parameter ids of
bracket-table parameters. Canonical instance at
`100/revisions/2025.toml:6297-6307` — formula
`renta-2025-cuota-escala-autonomica-sobre-base-liquidable-general`
writes casilla `0529` by looking up the base in
`renta-2025-escala-autonomica-{andalucia,aragon,asturias,...,murcia}-base-general`
according to the operator's CCAA binding. The companion formula at
`100/revisions/2025.toml:6313-6320` writes casilla `0531` (cuota
escala autonomica sobre minimo personal y familiar) with the same
dispatch table. Both formulas exist for each of the six committed
revisions (2020-2025) per the test fixture at
`test_modelo_100_autonomic_chain.py:38-58`.

The CCAA key is an enum string, routed via the `enum_binding_values`
parameter (Decimal-only `binding_values` keeps its strict contract).
The `lookup_bracket_by_ccaa` op expects
`enum_binding_values[binding_id]` to be a non-empty ASCII string CCAA
key and raises if missing or if the dispatch table omits the key.
Runtime at `_formula_runtime.py:206-252`.

### 2. Calc engine internals

#### 2.1 Entry points

`src/aeat/domain/calculations/registry/_formula_runtime.py` exposes
one public callable plus two pydantic record types:

`calculate_registry_snapshot(snapshot, *, inputs, date_context,
binding_values=None, enum_binding_values=None, relation_values=None)
-> RegistryCalculationResult` (`_formula_runtime.py:47-128`).
Signature: `inputs: Mapping[str, Decimal]` — manual casilla values
(rejects Decimal-bool and float), `date_context: Mapping[str, date]` —
at minimum `filing_period`, augmented at `_formula_runtime.py:66-67`
with `(snapshot.filing_year, 12, 31)` as a default, `binding_values:
Mapping[str, Decimal]` — Decimal channel for numeric bindings,
`enum_binding_values: Mapping[str, str]` — string channel (CCAA,
regime enum, etc.), and `relation_values: Mapping[str, Decimal]` —
resolved cross-modelo / cross-period values keyed by relation id.

Returns: `RegistryCalculationResult(modelo, revision, values,
entries)` (`_formula_runtime.py:36-44`) where `values` is the complete
`Mapping[str, Decimal]` of casilla values (inputs plus formula
outputs) and `entries` is the per-formula audit trace.

`RegistryCalculationEntry(formula_id, target, op, operand_refs,
operand_values, value, legal_refs, source_refs)`
(`_formula_runtime.py:21-33`) — one trace row per evaluated formula.
`operand_refs` includes both casilla ids (`expression.casilla`) and
binding/parameter/relation ids collected during recursion. This is the
data the Sheets exporter will read to build per-cell provenance
metadata.

`read_parameter(modelo_id, revision_id, parameter_id, *, date_context,
registry_root=None) -> Decimal` (`_formula_runtime.py:458-493`) —
read one registered parameter value without a snapshot. Used by
non-formula consumers.

#### 2.2 Loader and record shape

`_loader.py:42-47` `load_modelo_file(path)` — single-file modelo TOML
loader. LRU-cached on `(path, byte_count, modified_ns)` tuple so a
re-read after file mutation refreshes the cache.

`_loader.py:82-110` `load_modelo_directory(directory)` —
directory-layout loader. Reads `manifest.toml` (must not declare
`[revisions]`) plus every `revisions/*.toml` and merges them into one
`ModeloDefinition`. Same public API as the single-file loader.
Required for Modelo 100.

`_loader.py:150-175` `load_catalogue_file(path)` — loads the shared
legal/source catalogues from `registry/aeat/legal/`.

`_loader.py:178-248` `load_registry_tree(root)` — walks `legal/` plus
`modelos/`, returns a frozen `tuple[ModeloDefinition, ...]` plus the
`RegistryCatalogues`. Raises `RegistryLoadError` if a modelo appears
in both layouts.

`_build_modelo_definition_from_data` (`_loader.py:58-79`) validates
the merged TOML payload through `ModeloDefinition.model_validate` and
per-revision `ModeloRevision.model_validate`. Strict TOML; any unknown
key fails pydantic validation due to `extra="forbid"` on the
`RegistryModel` base (`_schema.py:116-119`).

#### 2.3 Pydantic record types

Authority record: `_schema.py:1095-1110` — `RegistrySnapshot` carries
`modelo`, `revision`, `filing_year`, `period`, plus the resolved
catalogue subsets and the indexed maps of each revision member type.
Constructed via `_snapshot.build_snapshot` (`_snapshot.py:22-50`) or
`_authority.ValidatedRegistryAuthority.snapshot`
(`_authority.py:67-92`); both back onto `_build_validated_snapshot`
(`_snapshot.py:64`) which calls `select_revision` from `_temporal.py`
and pre-derives the export layouts.

Per-revision record: `_schema.py:1035-1066` `ModeloRevision` carries
every array-of-tables member as a typed tuple.

Per-modelo record: `_schema.py:1069-1087` `ModeloDefinition`.

Construct resolution: `_constructs.py:13-96`. Constructs are the
registry's grouping primitive that materialises one filing surface;
`resolve_construct(revision, construct_id)` walks the indexed members
(`_CONSTRUCT_MEMBER_INDEXES` at `_constructs.py:39-69`) and returns a
`ResolvedConstruct` with typed `ResolvedConstructMember` entries by
kind.

#### 2.4 End-to-end calculation trace

The CLI surface `aeat app modelo work calculate` lives at
`src/aeat/entrypoints/cli/_modelo.py:892-975`. Flow:

1. Operator runs `aeat app modelo work calculate <work_unit_id>
   --casilla "01=10000" --casilla "02=4000" [--binding ...]
   [--borrador <id>]` at `_modelo.py:892-927`.
2. CLI parses `--casilla` / `--binding` strings to `dict[str, Decimal]`
   (non-decimal `--binding` values fall into `enum_binding_values`,
   supporting CCAA-style enum bindings); `_modelo.py:936-952`.
3. Calls `application.modelo.calculate_modelo_revision`
   (`_modelo.py:954-961`).
4. The application service
   (`src/aeat/application/modelo/_actions.py:467-680`): loads the
   work unit, resolves the registry snapshot via
   `ValidatedRegistryAuthority.snapshot(modelo, filing_year, period)`
   at `_actions.py:540-551`, resolves the Modelo 100 borrador snapshot
   bindings if applicable (`_actions.py:560-572`), merges operator
   overrides over backend bindings over borrador bindings (operator
   wins — `_actions.py:573-578`), then invokes
   `calculate_registry_snapshot(snapshot, inputs=..., date_context=...,
   binding_values=..., enum_binding_values=..., relation_values=...)`
   at `_actions.py:593-600`.
5. The runtime builds `_initial_values` from the manual casilla inputs
   (`_formula_runtime.py:131-149`), then walks
   `formula_evaluation_order(revision)` — a
   `graphlib.TopologicalSorter` walk at `_runtime_graph.py:78-88` that
   orders computed casillas by their cross-formula casilla
   dependencies. Each formula evaluates via `_evaluate_expression`
   recursion (`_formula_runtime.py:152-309`), rounds via
   `_apply_rounding` (`:420-427`), writes back into the `values`
   dict, and emits a `RegistryCalculationEntry` trace row.
6. The application service builds an `inputs_snapshot` and
   `binding_overrides` (canonical Decimal strings), derives the
   content-addressed `calculation_revision_id` via
   `derive_calculation_revision_id`
   (`domain/modelos/_calculation_revision.py:110-141`), persists the
   `CalculationRevision` to the catalogue repository
   (`_actions.py:622-641`), advances the work unit's
   `current_calculation_revision_id` pointer (`_actions.py:642-652`),
   and emits a `MODELO_CALCULATION_CREATED` bucket event
   (`_actions.py:653-659`).
7. CLI emits the resulting `CalculationRevision` payload
   (`_modelo.py:969-975`).

#### 2.5 Canonical persisted result type

`CalculationRevision` is the persisted record of one calculation
attempt. Pydantic v2, strict, frozen, `extra="forbid"`. Defined at
`src/aeat/domain/modelos/_calculation_revision.py:144-321`. Key fields
for Sheets-export consumers:

- `calculation_revision_id: str` — 64-char lowercase SHA-256 derived
  from `work_unit_id + inputs + overrides + outputs +
  source_transaction_ids + borrador_snapshot_id +
  bindings_sourced_from_borrador` via
  `derive_calculation_revision_id`. Same inputs produce same id, so
  re-runs are naturally idempotent.
- `work_unit_id: str` — parent work-unit id (also 64-char SHA-256
  content-addressed).
- `state: CalculationRevisionState` —
  `draft / verified_complete / filed / filed_superseded / discarded`.
- `casilla_values: Mapping[str, Decimal]` — every casilla the engine
  evaluated, formula outputs plus passthrough inputs.
- `inputs_snapshot: Mapping[str, str]` — canonical Decimal strings of
  the manual inputs (used for hash stability).
- `binding_overrides: Mapping[str, str]` — operator binding overrides
  (Decimal and enum), canonicalised.
- `source_transaction_ids`, `borrador_snapshot_id`,
  `bindings_sourced_from_borrador` — provenance pointers.
- `created_at`, `updated_at`, `verified_at`, `verified_by`,
  `filed_at`, `filed_by`, `superseded_at`, `discarded_at`,
  `discarded_by`, `discard_reason`, `amendment_kind`,
  `amends_filing_record_id`, `amendment_reason` — audit metadata
  enforced by state-specific invariants
  (`_calculation_revision.py:237-278`).

Storage: `CalculationRevisionCatalogue` at
`_calculation_revision.py:323-360`, persisted via
`CalculationRevisionCatalogueRepository` (referenced from
`_actions.py:481-486`). The catalogue is keyed by
`calculation_revision_id`; a parent work unit owns many revisions
through `for_work_unit(work_unit_id)`.

### 3. Existing Sheets work

`src/aeat/application/storage/calc_sheets/` does NOT exist; the
directory ls confirms the parent `application/storage/` itself does
not exist (it lives under `adapters/outbound/storage/`, not under
`application/`). The L3 ADR `2026-05-13-google-oauth-calc-sheets-adr`
placeholders the intent at
`/aeat-vault/_workspace/calc-modelo-<NNN>-<period>.gsheet` but no code
surface implements it.

The only `googleapiclient` imports in `src/aeat/` are at
`src/aeat/adapters/outbound/storage/_google_drive.py:123`
(`from googleapiclient.discovery import build`) and `:655`
(`from googleapiclient.http import MediaIoBaseUpload`). Both are
inside the Drive-v3 binary-blob `StorageProvider`, which uploads
`<hmac_prefix_8>--<label>.bin` octet-stream objects with Drive
`appProperties` metadata. There is no Sheets v4 client, no spreadsheet
builder, no cell-formula emitter, no protected-range writer.

The Sheets OAuth scope IS already negotiated. The `REQUIRED_SCOPES`
tuple at `src/aeat/adapters/outbound/google/_records.py:29-33`
requests `openid`, `userinfo.email`, `drive.file`, and
`https://www.googleapis.com/auth/spreadsheets`. So an operator who
completes the OAuth flow already grants the sheets-write scope; the
adapter layer just hasn't been built to consume it.

The locale translation files (`src/aeat/locales/*.yml`) contain
`sheets`/`Sheets` strings but those are CLI message fragments for
`app modelo` output, not Sheets API code.

### 4. Parity-test feasibility

#### 4.1 Direct `(modelo, period, inputs)` to `casilla map`

Yes. The shortest path is:

```
from aeat.core.paths import PROJECT_ROOT
from aeat.domain.calculations.registry import (
    ValidatedRegistryAuthority, calculate_registry_snapshot,
)

authority = ValidatedRegistryAuthority.load(
    PROJECT_ROOT / "registry" / "aeat",
    source_root=PROJECT_ROOT,
)
snapshot = authority.snapshot("130", filing_year=2026, period="1T")
result = calculate_registry_snapshot(
    snapshot,
    inputs={"01": Decimal("10000"), "02": Decimal("4000")},
    date_context={"filing_period": date(2026, 3, 31)},
    binding_values={...},
    relation_values={...},
)
casilla_map = dict(result.values)
trace = result.entries
```

This is the exact call shape exercised by every
`test_modelo_*_registry.py` test under
`src/aeat/domain/calculations/registry/`. The runtime is pure (no I/O
during evaluation), so the same call repeated against the same
snapshot always produces the same Decimal result — this is the
bit-exactness guarantee the Sheets engine has to mirror in spreadsheet
formulas.

#### 4.2 Deterministic snapshot-test patterns

The registry test suite contains 33 `test_modelo_*` files under
`src/aeat/domain/calculations/registry/`. The canonical deterministic
pattern is at `test_formula_runtime.py:61-86`:

```
def test_registry_formula_runtime_calculates_committed_modelo_in_dependency_order(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
        inputs={...},
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={_PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000")},
    )
    order = {entry.target: index for index, entry in enumerate(result.entries)}
    assert order["03"] < order["04"] < order["07"] < ...
```

The `committed_modelo_130_snapshot` fixture comes from a package-level
`registry_snapshot` fixture (`test_formula_runtime.py:30-34`) that
builds against the live registry root. The `formula_evaluation_order`
invariant test asserts the topological order; arithmetic asserts
ground out against externally-sourced expected values per the
no-tautological-calculation-tests rule. The 33 per-modelo test files
predominantly assert structural / graph-wiring invariants
(`operand_refs`, `formula_targets`, `relation_ids`, casilla counts,
binding presence) — that authority surface is exactly what a
Sheets-export parity test would call.

The pattern most directly aligned with bit-exact Sheets parity is
`test_modelo_100_autonomic_chain.py:38-58`. It parametrises across 6
ejercicios x 2 target casillas x 15 CCAA = 180 cells and asserts
dispatch-table membership for every cell. The same parametrisation
pattern can be reused to assert per-CCAA Sheets formulas match
per-CCAA Python outputs.

#### 4.3 Canonical inputs to known-output fixtures

Five `corpus/parity_replays/renta_web_open/*.json` fixtures exist for
Modelo 100 / 2025 across five CCAA. Schema (from
`modelo-100-2025-employee-default-minimo.json:1-26`): `expected` map
of label to numeric string, `observed` map of label to es-locale
string, `expected_by_casilla` map of casilla id to numeric string,
`observed_by_casilla` map of casilla id to es-locale string, and a
`raw_evidence_locator` URL pointing at the AEAT renta-web-open
simulator. These are externally-sourced inputs (AEAT's own simulator);
they satisfy the no-tautological-calculation-tests rule.

The broader parity infrastructure is the workbook-parity + parity-tape
surface in `src/aeat/domain/calculations/registry/`:

- `_workbook_parity.py` defines `WorkbookParityRunReport`,
  `WorkbookParityComparison` (status `match/mismatch/not_run`,
  tolerance defaults to `0`), `SyntheticInputSet`, and the full
  discovery + verification backend at `verify_workbook_backend`.

- `_parity_tapes.py` defines `ParityScenario` (modelo, revision,
  filing_year, period, workbook_path, synthetic_input, output_cells,
  registry_outputs, date_context, relation_values, tolerance) and
  `run_parity_scenario` / `replay_parity_tape`. These produce archived
  JSON `ParityTape` records that can be replayed bit-for-bit against
  the current registry. The replay test asserts current calculation
  matches stored tape — this is the strict-parity contract the
  Sheets-export engine will need to extend.

- `WorkbookParityReference` entries in registry TOML (`303.toml:32-40`
  example) declare per-modelo workbook parity binding:
  `workbook_source`, `formula_coverage` (one of
  `formula_form / static_layout / record_design_layout /
  unsupported_binary_xls`), `runner_required` flag, `output_cells` map
  of output_id to `WorkbookCellRef`, and `tolerance` (Decimal).

No equivalent corpus of `(modelo, period, inputs)` to `casilla_map`
snapshot tests exists yet for direct registry parity assertions; the
L3 plan (`2026-05-13-cli-workflow-redesign-epic-plan`) places this at
the per-modelo aggregation pipeline test surface, currently unbuilt.

### 5. What is NOT there — architect's gap list

For an ADR drafter aiming at a schema-to-Sheets engine:

- **No Sheets v4 client.** Nothing imports
  `googleapiclient.discovery.build("sheets", "v4", ...)`; no
  protected-range writer; no named-range or conditional-format
  emitter; no batchUpdate scaffolding. The Drive v3 binary provider at
  `adapters/outbound/storage/_google_drive.py` is a reference for the
  auth + service-factory pattern but does not generalise to
  spreadsheets.

- **No formula translator.** No code maps a `FormulaExpression` graph
  to Sheets formula text. The op corpus is small (22 ops); a
  translator is a closed-form recursive function over the
  `_evaluate_expression` shape, except for `lookup_bracket` /
  `lookup_bracket_by_ccaa` which need a hidden `_Tariffs` sheet plus
  `INDEX/MATCH` (or `VLOOKUP`) plus `IF` chains for fixed-addition +
  marginal-rate piecewise-linear arithmetic.

- **No cell-address allocator.** The Sheets engine needs a
  deterministic casilla-id to `Entradas!Bn` / `Calculos!Bm` cell
  mapping. The registry has casilla-ordering data
  (`revision.casillas` is an ordered tuple) but no cell-address
  authority.

- **No per-casilla provenance projector.** The Sheets export needs a
  per-casilla `(label, formula, value, oracle, normativa,
  ultima_actualizacion, version_registro)` projection. Existing data
  sources: `RegistryCalculationEntry` provides
  `formula_id, target, op, operand_refs, operand_values, value,
  legal_refs, source_refs`; the registry catalogues provide
  `LegalReference` with article and permalink; the registry SHA can
  be derived via the loader's TOML fingerprints. No record type
  combines them.

- **No `application/storage/` subpackage.** L3 plan placeholders P07
  of W30 at `src/aeat/application/storage/calc_sheets/`; the parent
  `application/` carries other domains (modelo, filing, review,
  verification, transactions, registry...) but no storage sibling.
  The hexagonal layout mandate places Drive/Sheets adapter code under
  `adapters/outbound/google/` and `adapters/outbound/storage/`; the
  orchestration belongs in `application/storage/`.

- **No two-way Inputs sheet to substrate hydrator.** The ADR
  (`2026-05-13-google-oauth-twoway-adr`) covers Tier-1 domain Sheets
  two-way; calc-sheets ADR keeps calculation sheets read-only beyond
  the Entradas sheet. The hydrator would read Entradas inputs and
  re-run `calculate_modelo_revision` with `--casilla` overrides (the
  same CLI entry point operators use today). Existing code paths
  support this; nothing wires Sheets to input parsing.

- **No registry SHA-256 watermark surface.** The Procedencia sheet's
  `Version registro` column needs a stable digest of the registry
  source files at export time. The loader records
  `(path, byte_count, modified_ns)` fingerprints per file
  (`_loader.py:251-254`) but no aggregate-digest helper exists; one
  will be needed for the export's audit trail.

### 6. Reference Snapshot

Module(s): `aeat.domain.calculations.registry` (formula runtime,
schema, loader, snapshot, runtime graph, workbook parity, parity
tapes, authority, constructs); `aeat.domain.modelos` (calculation
revision record + catalogue); `aeat.application.modelo`
(`calculate_modelo_revision` orchestrator); `aeat.entrypoints.cli`
(`app modelo work calculate` surface); `aeat.adapters.outbound.storage`
(Drive v3 reference); `aeat.adapters.outbound.google` (OAuth + scope
catalogue).

File(s):

- `registry/aeat/modelos/100/manifest.toml` plus
  `registry/aeat/modelos/100/revisions/2020.toml` ...
  `2025.toml`
- `registry/aeat/modelos/{111,115,123,130,131,180,184,
  190,193,200,202,232,303,308,309,322,347,349,353,360,
  369,390,720,840}.toml`
- `src/aeat/domain/calculations/registry/_formula_runtime.py`
- `src/aeat/domain/calculations/registry/_loader.py`
- `src/aeat/domain/calculations/registry/_schema.py`
- `src/aeat/domain/calculations/registry/_constructs.py`
- `src/aeat/domain/calculations/registry/_snapshot.py`
- `src/aeat/domain/calculations/registry/_authority.py`
- `src/aeat/domain/calculations/registry/_runtime_graph.py`
- `src/aeat/domain/calculations/registry/_workbook_parity.py`
- `src/aeat/domain/calculations/registry/_parity_tapes.py`
- `src/aeat/domain/calculations/registry/__init__.py`
- `src/aeat/domain/calculations/registry/test_formula_runtime.py`
- `src/aeat/domain/calculations/registry/test_modelo_100_autonomic_chain.py`
- `src/aeat/domain/calculations/registry/test_modelo_303_registry.py`
- `src/aeat/domain/calculations/registry/test_modelo_130_registry.py`
- `src/aeat/domain/modelos/_calculation_revision.py`
- `src/aeat/application/modelo/_actions.py`
- `src/aeat/application/registry/__init__.py`
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/adapters/outbound/storage/_google_drive.py`
- `src/aeat/adapters/outbound/google/_records.py`
- `corpus/parity_replays/renta_web_open/*.json` (5 fixtures)

Related: `[[2026-05-13-google-oauth-calc-sheets-adr]]`,
`[[2026-05-13-google-oauth-twoway-adr]]`,
`[[2026-05-13-google-oauth-plan]]`.
