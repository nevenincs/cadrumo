---
tags: ["#research", "#calculation-source-connectivity"]
date: "2026-05-20"
modified: '2026-05-20'
related:
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
---

# `calculation-source-connectivity` research: `bridge financial input domains into modelo calculations`

This research maps why user-entered or imported financial facts can exist in
ledger, invoice, inventory, profile, and property domains without reliably
reaching the modelo calculation engine. The immediate operator symptom is that
classified transactions can be present in the CLI ledger while a modelo
calculation still returns zero-valued casillas. The broader architectural
question is how every future financial source should connect to registry
bindings without violating the hexagonal direction.

## Findings

The codebase already contains the core pieces for a ledger-to-modelo bridge,
but the operator-facing calculate path is not consistently enrolled into that
bridge.

`src/aeat/domain/transactions/_repository.py` defines the bucket-scoped
`TransactionCatalogueRepository`, stores `TransactionCatalogue` in secure
FINANCIAL envelopes, and explicitly notes that transaction ids are only unique
inside a bucket. `src/aeat/domain/transactions/_models.py` defines the
classified `Transaction` and `TransactionCatalogue` records that the ledger
actions mutate.

`src/aeat/application/ledger/_actions.py` owns the CLI-backed lifecycle for
manual ledger rows, imports, updates, classification, allocation, evidence
attachment, split/merge, archive, stash, remove, export, and reset. It also
guards mutation against finalized modelo references through
`_blocking_modelo_references`, `_transaction_modelo_source_ids`, and
`_catalogue_modelo_source_ids`. This means the ledger already knows modelo
revisions can depend on ledger transaction ids.

`src/aeat/application/aggregation/_iva_ledger.py` projects active classified
ledger transactions into `IvaLedgerObservation` rows. It gates by period,
currency, direction, business classification, proportionality, required IVA
facts, and canonical IVA rate. It returns typed issues rather than silently
dropping every invalid row.

`src/aeat/application/aggregation/_renta_ledger.py` projects active classified
ledger transactions plus purchase invoice evidence into first-slice Renta
deductible expense observations. It gates by direction, currency, business
classification, spending category, category profile, purchase evidence,
period, and deductibility result.

`src/aeat/domain/calculations/registry/_bindings.py` declares the registry-side
binding resolvers: `resolve_ledger_iva_aggregation_binding_values`,
`resolve_ledger_renta_expense_aggregation_binding_values`,
`resolve_invoice_binding_values`, `resolve_counterpart_binding_values`, and
other source-specific resolvers. The registry deliberately consumes typed
observations or structural protocols, not application repositories.

`src/aeat/domain/calculations/registry/_schema.py` lists supported binding
source literals in `DataBindingDefinition`, including `ledger_iva_aggregation`,
`ledger_renta_expense_aggregation`, `invoice`, `payable_invoice`,
`collectible_invoice`, `ledger_transaction`, `purchase_invoice_evidence`,
`profile`, `previous_filing`, `withholding`, `foreign_asset`, and other
source families.

`src/aeat/application/aggregation/_modelo_bindings.py` is the existing
application bridge for ledger-backed modelo bindings. Its
`resolve_modelo_ledger_binding_values_from_repositories` function loads the
bucket transaction catalogue, runs the IVA and Renta ledger projections only
when the selected revision declares those binding sources, resolves registry
binding values, collects typed issues, and records `source_transaction_ids`.

`src/aeat/application/modelo/_actions.py` has two calculate paths. The lower
level `calculate_modelo_revision` runs the registry formula engine with caller
casilla inputs, caller binding values, backend binding values, enum bindings,
relation values, borrador values, and IVA wallet decisions. The higher level
`calculate_modelo_revision_from_bucket_aggregation` resolves bucket ledger
bindings first, rejects caller overrides of ledger-owned bindings and bound
casillas, maps available bindings to bound casilla inputs, passes
`source_transaction_ids`, and then delegates to `calculate_modelo_revision`.

`src/aeat/entrypoints/cli/_modelo.py` currently routes `app modelo work
calculate` to the lower-level `calculate_modelo_revision`, after parsing
manual `--casilla`, `--binding`, and `--relation` inputs. This is the critical
connectivity gap: the CLI calculate command bypasses the existing
bucket-aggregation bridge, so classified ledger transactions do not feed the
default operator calculation path.

`src/aeat/application/modelo/test_bucket_aggregation_flow.py` proves that the
bridge itself can compute non-zero Modelo 303 inputs from a real secure-object
transaction catalogue and persist source transaction ids. The missing test is
the real CLI operator path: seed the ledger through application or CLI behavior,
run `aeat app modelo work calculate`, and assert the persisted revision carries
ledger-derived binding overrides, bound casilla inputs, typed observations, and
source transaction ids.

The committed registry data confirms direct ledger IVA bindings for IVA
modelos such as 303, 309, 322, 353, and 390. The committed Renta ledger expense
bindings observed in the data are on Modelo 100 2025 first-slice expense
bindings. The reported Modelo 130 all-zero symptom should be treated as part of
the same source-enrollment class, but not assumed to use the exact same direct
`ledger_renta_expense_aggregation` source without a model-specific registry
audit.

Existing connectivity outside the immediate ledger bridge is uneven.
`src/aeat/application/aggregation/_service.py` defines a central per-modelo
aggregation service contract, but it is hardcoded to retenciones, counterpart,
and foreign asset providers. `src/aeat/application/aggregation/_registry_provider.py`
connects the per-modelo counterpart service to registry bindings, but only for
the currently supported counterpart path. This is useful tissue, but not yet a
generic mesh for all source families.

`src/aeat/application/invoices/_linking.py`, `src/aeat/application/invoices/_queries.py`,
and `src/aeat/application/invoices/_projection.py` provide invoice-to-ledger
matching and review projections. The registry has invoice and counterpart
binding resolvers, but there is no general calculation source resolver that
automatically asks invoice repositories for the observations a selected modelo
revision declares.

`src/aeat/domain/fincas` contains property, rent, expense, amortization, and
imputation domain logic. The discovery pass found no application-level source
adapter that projects those facts into modelo binding values. This is a
separate instance of the same architectural gap.

`src/aeat/application/inventory/_service.py` persists inventory ledgers to JSON
under `Settings.aeat_ledgers_dir`, while the broader secure storage direction
uses `SecureObjectRepository` and envelope-bound repositories. This is a
durability and consistency split before inventory can safely become a modelo
source for amortization or stock-related calculations.

Secure storage and profile lifecycle already provide reusable patterns:
bucket-bound secure repositories, typed envelopes, active bucket resolution,
profile path projection, and bucket event histories. The missing abstraction is
not storage itself; it is a canonical application-level resolver registry that
uses those repositories to produce calculation source observations.

External grounding supports the same direction. Cockburn's ports-and-adapters
article frames the application as independent from UI and database adapters,
which matches the project rule that CLI and persistence must not own domain
logic. Pydantic v2 supports strict model configuration and extra-field
forbiddance for boundary contracts. Python Protocol structural subtyping
supports the registry pattern already used for Renta expense observations:
domain calculation code can require an observation shape without importing the
application or source domain implementation.

## Recommended architecture

Promote the existing ad hoc bridge into a canonical calculation source mesh in
`aeat.application.aggregation`.

The mesh should expose a small application port:
`CalculationSourceContext` carries bucket id, modelo, filing year, period,
registry revision, selected profile facts, repositories, and clock.
`ModeloSourceResolver` declares supported registry binding sources and returns
a typed `CalculationSourceResolution`. A resolution carries decimal binding
values, enum binding values, bound casilla inputs, row values when needed,
source object refs, issues, and provenance.

The mesh should run all resolvers applicable to the selected revision, detect
unhandled binding sources, reject duplicate writes to the same binding or bound
casilla unless a declared precedence rule exists, and return one merged
resolution to `calculate_modelo_revision`.

`calculate_modelo_revision_from_bucket_aggregation` should become either the
first built-in resolver set or a compatibility wrapper over the mesh. The CLI
`app modelo work calculate` should call the mesh-backed path by default.
Manual `--binding` and `--casilla` inputs should remain available only for
sources that no automatic resolver owns, or as explicit operator overrides
that are rejected on collision with source-owned bindings.

Initial resolver enrollment should include ledger IVA aggregation, ledger
Renta expense aggregation, prior filing and relation sources, Modelo 100
borrador prefill, IVA compensation wallet, invoice and counterpart sources,
withholding sources, foreign assets, profile enum bindings, property/fincas,
and inventory/amortization once their storage path is canonical.

Every resolver must be an application-layer adapter over one or more domain
repositories. The registry remains pure: it validates binding declarations and
aggregates typed observations, but it must not import storage, CLI, workflow,
or profile lifecycle modules.

Testing should use real secure repositories and real CLI/application flows.
The first regression must seed bucket-local ledger transactions, run the CLI
calculation command, and assert non-zero bound Modelo 303 values, populated
`source_transaction_ids`, and typed observations. Future tests should verify
missing-source diagnostics and no silent all-zero output when a source-backed
modelo has available source data but no enrolled resolver.
