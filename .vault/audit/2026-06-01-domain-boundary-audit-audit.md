---
tags:
  - '#audit'
  - '#domain-boundary-audit'
date: '2026-06-01'
modified: '2026-06-01'
related: []
---



# `domain-boundary-audit` audit: `Domain ownership and cross-boundary outlier audit`

## Scope

Rolling base ledger for the semantic domain-ownership campaign. This document
maps every top-level package under `src/aeat/domain/` and `src/aeat/application/`
against what it *claims* to own (its `__init__` docstring and public surface) and
against where the corresponding functional concept *actually* lives in the
codebase. The target is the outlier: a model or behaviour that names itself for
one domain but is implemented, re-implemented, shadowed, or shimmed inside
another.

Method is deliberate and repeatable: for each functional concept, run a
`vaultspec-rag search --type code --port 8766 --max-results 14` cluster query,
read the directory clustering rather than the single top score, then verify the
exact sites with `rg`. RAG is the discovery instrument (it clusters by meaning
across vocabulary mismatch); `rg` is the confirmation instrument (it pins the
exact symbol and constraint shape). Every "X belongs in Y" candidate is run
through the substitutability pre-filter before it is allowed to become an
actionable finding: if the proposed canonical home Y carries constraints X does
not, the site is a constraint-shape divergence, not a duplication cluster, and
is recorded as checked-and-excluded rather than actionable.

Findings accrue here continuously across passes. Each carries a stable ID
(`DB-NN`), a severity, the RAG+`rg` evidence that surfaced it, and a concrete
remediation or an explicit exclusion rationale. The honesty-review and
swarm-audit cadence rules govern when this ledger is re-swept.

Baseline inventory: `domain/` holds 22 packages (552 `.py` files); `application/`
holds 25 packages (401 files); `adapters/` 369; `entrypoints/` 142; `core/` 101.
Total tracked Python surface is 1701 files.

## Findings


### DB-01 (MEDIUM) — `profile` / `user_profile` / renta family-facts have no single canonical home

**Pathway:** domain ownership smear across naming-collision packages.

The concept "taxpayer personal/family facts" is scattered with no canonical
owner. `domain/profile` declares itself *"The operator's tax-residence profile"*
and *"intentionally separate from financial usage-ratio profiles"*, yet its
actual contents are renta/IRPF family facts: `_descendant_facts.py`,
`_marriage_facts.py`, `_deduccion_maternidad.py`, `_renta_codes.py`, `family.py`
(*"Typed repeated family-member facts consumed by Modelo 100 bindings"*), and
CCAA residence. A parallel `domain/user_profile` declares itself the *"Central
user-profile schema contract"* (census/taxpayer identity, registry contract,
portable export), and `application/user_profile` owns the persistence
(repository, lifecycle, projections, censo_sync). A third site, `core/profile.py`,
is one of only two non-test importers of `domain/profile`.

A RAG cluster query for "taxpayer residence and family descendant facts profile"
scored low (top 0.36) and scattered across `domain/profile/_descendant_facts`,
`domain/profile/family.py`, `user_profile`, and registry TOML
(`renta-2025-family-descendant-*`, `m210-*-profile-country-of-fiscal-*`, all
`source = "profile"`). Low-score scatter with no dominant cluster is the
signature of a concept that has no canonical home — three packages each own a
slice and the registry binds them by the string `"profile"`.

**Data at risk:** newcomers cannot locate the authority for family/descendant
facts; renta bindings reach into a package named for tax-residence; the
`profile` vs `user_profile` split is a documented intentional separation whose
boundary is not legible from the names.

**Remediation (proposed, not yet actioned):** decide the canonical home and true
name for the renta family-facts surface so the name stops claiming a
residence-profile domain it does not own. Deferred pending coordination (this is
a heavily-imported package, see pass-2 evidence below).

**Pass-2 evidence (2026-06-01).** The package is not two concerns but **three**.
`rg` on class definitions in `domain/profile` (non-test) returns:

- *Tax residence (legitimately matches the name):* `TaxResidenceProfile`,
  `FiscalResidency`, `TaxResidenceProfileError`, `ProfileKey`,
  `ProfileKeyRequirement`.
- *Renta / Modelo-100 family facts (outlier — reads as `renta` territory):*
  `RentaFamilyProfile`, `RentaDescendantProfile`, `RentaAscendantProfile`,
  `RentaDeclaracionType`, `RentaSexCode`, `RentaMaritalStatus`,
  `RentaDisabilityGrade`, `SituacionFamiliar`, plus `DescendantInfo`,
  `_marriage_facts`, `_deduccion_maternidad`, `_incremento_guarderia`. `family.py`
  self-describes these as *"consumed by Modelo 100 bindings"*.
- *Inventory / asset / amortization (second outlier — reads as `inventory`/`ledger`
  territory):* `AssetRecordError`, `AssetValidationError`, `AmortizacionLedgerError`,
  `InventoryLedgerError`, `InventoryValidationError`, plus a `profile/inventory/`
  subpackage. These error families live in `domain/profile/_errors.py` alongside
  the residence errors with no domain relationship to a tax-residence profile.

The single `_errors.py` carrying residence + asset + inventory + amortization
errors is the structural tell that the package is a catch-all, not a domain.

**Import-graph facts.** `domain/profile` has 23+ non-test importers spanning every
layer (`adapters/persistence/profile`, `application/inventory`,
`application/modelo/_actions` and `_profile_binding`, `application/review`,
`application/wizard` ×4, `application/workflow`, `core/profile`,
`core/errors/registry`, `diagnostics/profile`, four `entrypoints/cli` modules,
and `application/user_profile/_keys_validation`). Two coupling hotspots:
`application/modelo/_actions.py` imports **both** `domain/profile` and
`domain/user_profile`; `application/user_profile/_keys_validation.py` (the
app-layer of the *other* profile package) reaches into `domain/profile`. Any
split or rename is therefore a multi-consumer atomic relocation, not a local
edit — sequence it per the atomic-relocation rule (canonical move + every
consumer in one commit, `relocation:<symbol>` subject tag).

### DB-02 (LOW / EXCLUDED) — `invoices` and `transactions` are shared-vocabulary twins, not a duplication cluster

**Pathway:** parallel naming that survives the substitutability pre-filter as a
genuine divergence.

Both packages carry near-identical claims: *"Immutable {invoice,transaction}
catalogue surface for the financial pipeline"*, both expose `_models.py`
(*"Strict immutable models for the X catalogue"*), `_service.py`, and an
`__init__` of the same shape. A RAG query for "immutable financial catalogue of
invoices and transactions" returned a very tight high-score cluster (0.95 / 0.93)
pairing the two `__init__` modules, which is exactly what a duplication cluster
would look like at the docstring layer.

`rg` on the actual model shapes refutes duplication. `Invoice` carries
`InvoiceLine`, counterparty identity, `base_total`/`iva_total`/`grand_total`,
`payment_status`, retention fields. `Transaction` carries
`ClassificationHistoryEntry`, `TransactionEvidenceProvenanceEntry`,
`TransactionEditLineageEntry`, `TransactionLifecycleLineageEntry`,
`SplitLineage`, with pervasive `min_length`/`max_length` constraints the invoice
side does not carry. The two are deliberately linked (an `InvoiceCatalogue`
references transactions; a `LinkInconsistency` model describes one-sided links
*between the two catalogues*), so the parallel naming is a shared **catalogue
vocabulary**, not a shared implementation.

**Disposition:** EXCLUDED from actionable work by the substitutability
pre-filter. Recorded here so a future pass does not re-flag the same lexical
similarity. The only residual nit is that the twin docstrings invite the
confusion; no code change is warranted.

### DB-03 (LOW) — `domain/modelos` docstring under-claims the package's real surface

**Pathway:** documentation-vs-reality drift at a domain root.

`domain/modelos/__init__.py` docstring reads only *"Modelo identifiers."*, but the
package owns the modelo persistence and identity core: `_calculation_repository`,
`_filing_repository`, `_verification_repository`, `_calculation_revision`,
`_filing_record`, `_runtime_repository`, `_work_unit`, `_row_models`. RAG for
"modelo calculation revision filing verification repository" confirms the durable
records (`ModeloRecord`, filing-record store) live here while the
calculate/verify/file *orchestration* correctly lives in `application/modelo`
(`_actions.py`, `_export.py`). The hexagonal split (entities/repos in `domain`,
use-case flow in `application`) is sound; only the root docstring is stale and
misleads a reader into thinking the package is a thin id module.

**Remediation:** rewrite the `domain/modelos` package docstring to describe its
true surface (modelo identity + calculation/filing/verification repositories +
revisions + work units), cross-linking the core structs per the
core-struct-docstring-links rule. Low-risk, single-file, doc-only.

### DB-04 (NOTE) — `modelos` (plural) vs `modelo` (singular) pluralization split is intentional but undocumented

`domain/modelos` (plural) and `application/modelo` (singular) is a real
naming inconsistency, but it tracks the hexagonal layer boundary (domain entities
vs application use-cases) rather than a duplication. Recorded as a navigability
nit, not a defect. No action unless a future convention pass standardizes
layer-pluralization.

### DB-05 (HIGH) — duplicate `declaration_key` / `update_declaration_pointer` in `application/workflow` with silent key divergence

**Pathway:** same symbol defined twice in one package, exported version shadows the other.

`declaration_key(modelo, period)` is defined in both `application/workflow/_models.py:168`
and `application/workflow/_engine.py:1295`, and `update_declaration_pointer` likewise
at `_models.py:293` and `_engine.py:1300`. The two `declaration_key` bodies are **not
equal**: `_models.py` returns `f"{modelo.strip()}:{period.strip()}"`; `_engine.py`
returns `f"{modelo.strip()}:{period.strip().upper()}"`. `__init__.py` imports and
re-exports the `_engine` versions (lines 42-43, 114/121), so all package-external
consumers receive the upper-casing variant, while `_models.py`-internal callers use
the non-upper-casing variant. A state-store key written through one path and looked
up through the other diverges whenever `period` carries lowercase letters (e.g. raw
`"2025q1"` vs `"2025Q1"`). Verified by `rg` on both definitions and the `__init__`
re-export ordering.

**Data at risk:** state-store key mismatch — a declaration written via the models-path
key is invisible to an engine-path lookup (and vice-versa) for any non-normalized
period token. Latent today only if all period tokens are pre-normalized upstream;
becomes a live correctness bug the moment a lowercase token reaches either path.

**Remediation (audit-only; not actioned):** collapse to one canonical
`declaration_key`/`update_declaration_pointer` (one home, the engine's upper-casing
variant is the safer normalizer), delete the duplicate, update the `_models.py`
internal callers, land as one atomic no-shim commit per the atomic-relocation rule.
Add a structural test asserting a single definition and round-trip key stability.

### DB-06 (MEDIUM) — period parsing re-implemented in `application` against `domain/period.py`

**Pathway:** domain primitive re-implemented in two application packages.

`domain/period.py` is the canonical filing-period parser (`parse_canonical_period`,
`period_start_date`, `period_end_date`, `PeriodValidationError`) and is already
imported directly by `application/filing`, `application/modelo/_actions`,
`application/verification/_verify`, and `application/registry`. Two sites re-derive
the same token-shape→(year, quarter, date-bounds) logic instead:
`application/aggregation/_models.py:81` (`class Period` with its own `_PERIOD_RE`,
`_QUARTER_MONTHS`, `start`/`end` computed properties) and
`application/workflow/_engine.py:81-119` (`_period_to_year`, `_registry_period_token`).

**Substitutability note:** `domain/period.py` is functions-only; the aggregation
`Period` adds a pydantic model wrapper the domain lacks, so the model itself is not a
literal duplicate — but the *arithmetic* (regex, quarter-month map, date bounds) is.
The workflow helpers are a closer duplicate; the only divergence is error type
(`PeriodValidationError`/`ValueError` vs `WorkflowError`), and the engine call site
already catches `ValueError`, so substitution is structurally clean.

**Remediation (audit-only):** route the workflow helpers through
`parse_canonical_period`; promote the period arithmetic (and optionally a canonical
`Period` model) into `domain/period.py` and have aggregation import it. Verify against
the existing domain parser tests.

### DB-07 (MEDIUM) — `application/topics` types force a `core → application` upward import (hexagonal inversion)

**Pathway:** persisted registry types placed one layer too high, inverting the
dependency direction.

`Topic`, `TopicCatalogue`, `TopicNotFoundError`, and `load_topic_catalogue` are
defined in `application/topics/__init__.py`, yet they are consumed by `core`:
`core/resources/_repos/topics.py:10,20` imports `from ....application.topics import
TopicCatalogue / load_topic_catalogue`, and `core/errors/registry/_application.py:194`
references `aeat.application.topics.TopicNotFoundError`. The topics types import only
from `core.*` themselves, so their placement in `application/` is what forces `core`
to depend upward on `application` — a violation of the accepted hexagonal direction.

**Remediation (audit-only):** relocate the topics catalogue types to `core/` (or a
`domain/`-level registry module) so the repository in `core/resources` sits at or
below the layer of the types it wraps. Atomic relocation with consumer updates.

### DB-08 (MEDIUM) — `application/wizard/_verifier` re-derives `SituacionFamiliar` legal rule

**Pathway:** regulatory rule re-implemented in application where the domain enum
already encodes it.

`application/wizard/_verifier.py:132-145` defines local frozensets
`_JOINT_INELIGIBLE = {PAREJA_HECHO_NO_REGISTRADA}` and `_MONOPARENTAL_REQUIRED =
{SOLTERO, SEPARADO_DIVORCIADO}` and applies them inline. The domain enum
`domain/profile/_renta_codes.py:82` `SituacionFamiliar` already encodes the same Art.
82.1.2° LIRPF rule: `.conjunta_eligible()` returns `True` for exactly the complement
of `_JOINT_INELIGIBLE`, and the monoparental subset matches the enum docstring. The
verifier re-derives the legal grounding rather than calling the domain method.

**Substitutability note:** the domain methods carry no extra constraints; the move is
clean. (NB: `SituacionFamiliar` lives in `domain/profile` — itself flagged in DB-01 as
mis-homed renta logic; DB-08's fix should target whatever DB-01 resolves the home to.)

**Remediation (audit-only):** call `sf.conjunta_eligible()` and the domain
monoparental predicate from the verifier; delete the local frozensets. Grounding
already cited in the domain docstring.

### DB-09 (LOW-MEDIUM) — `setup` accepts `iva_regime` as bare `str`, bypassing the `IVARegime` enum

**Pathway:** closed value set typed as raw string at an application boundary.

`application/setup/_contracts.py:28` types `iva_regime` as a constrained `str`;
`_service.py:20` passes it through raw. The canonical closed set is
`domain/deadlines/_models.py:23` `IVARegime` (`general`, `simplificado`,
`recargo_equivalencia`, `reagp`, `exento`). Per the architecture-boundaries rule
(type every constant-like axis; hint accepted values at the CLI boundary) this should
be the enum. Agent-reported (UNVERIFIED) sub-lead: tests pass uppercase `"GENERAL"`
while `IVARegime.GENERAL.value == "general"`, suggesting a latent fixture/case
mismatch — verify before acting.

**Remediation (audit-only):** type the field `IVARegime`; let the loader hydrate at
boundary; confirm/repair the fixture casing.

### DB-10 (LOW) — `operator_surface.SourceKind` duplicates `core.aggregation.AggregationSourceKind`

**Pathway:** parallel enum that is a strict subset of an existing core authority.

`application/operator_surface/_models.py:37` defines `SourceKind` with 4 members
(`ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`,
`collectible_invoice`) — identical string values to a strict subset of
`core/aggregation.py` `AggregationSourceKind` (which also has `invoice`). The core
enum is more permissive (no extra constraints), so the substitutability pre-filter
passes; the operator-surface subset is a duplication, not a divergence. The missing
`invoice` member is an intentional CLI-parser restriction.

**Remediation (audit-only):** express the operator-facing set as a `Literal`/frozenset
slice over `AggregationSourceKind` rather than a parallel enum, to prevent drift.

### DB-11 (LOW-MEDIUM) — `IvaInvoiceClassification` export asymmetry across `iva` and `invoices`

**Pathway:** a class whose private module claims it but whose package root disowns it,
re-exported as canonical by a different domain.

`IvaInvoiceClassification` is defined at `domain/iva/_invoice_classification.py:93` and
listed in that private module's own `__all__`, but is **absent** from
`domain/iva/__init__.py`'s `__all__` (which exports only the sibling
`IvaInvoiceClassificationCriteria`). It is re-exported as a first-class public symbol
from `domain/invoices/__init__.py:21,46`, and `rg` confirms its only importers are the
`invoices` package. The class is not used inside `iva` itself.

**Remediation (audit-only):** pick one canonical home. Since the type is invoice-shaped
and consumed only by `invoices`, the cleaner resolution is to make `invoices` the
canonical owner and drop the claim from the `iva` private module's `__all__` — or, if
it is genuinely an IVA primitive, export it from `iva/__init__` and have `invoices`
re-export plainly. Either way remove the asymmetry.

### DB-12 (MEDIUM) — `domain/normatives` docstring promises a `NORMATIVE_CATALOGUE` singleton that does not exist

**Pathway:** documented public API surface absent from the implementation.

`domain/normatives/__init__.py` docstring example imports `NORMATIVE_CATALOGUE`, but the
`_LazyCatalogue` class is defined and never instantiated/exported; `__all__` omits it.
Callers must use `load_catalogue()`. No runtime breakage today (nobody imports the
phantom symbol) but the documented contract is false. Agent-reported; class inventory
consistent with the claim — recommend a quick confirm read before acting.

**Remediation (audit-only):** either instantiate and export
`NORMATIVE_CATALOGUE = _LazyCatalogue()` in `__all__`, or correct the docstring to show
`load_catalogue()`. Doc/one-symbol change.

### DB-13 (MEDIUM) — `domain/auth` parent package exposes none of the surface its docstring claims

**Pathway:** package docstring claims a public API the `__init__` does not export.

`domain/auth/__init__.py` is docstring + `from __future__` only — no imports, no
`__all__` — yet the docstring claims *"Domain layer for AEAT auth protocol primitives
(apoderamientos, providers)."* Consumers reach the real surface only via
`from aeat.domain.auth.apoderamientos import …` (`application/auth/_apoderado.py:44`,
`core/resources/_repos/apoderamientos.py:15`). Additionally, no `providers` subpackage
exists, so part of the claim is aspirational.

**Remediation (audit-only):** either re-export the `apoderamientos` public surface from
`domain/auth/__init__.py` (matching the subpackage's `__all__`) and drop the
unimplemented `providers` clause, or flatten to `domain/auth` as a single module.

### DB-14 (NOTE) — closed regulatory value sets live in `application/aggregation` instead of `core/`

`application/aggregation` declares several closed regulatory StrEnums —
`RetencionScheme` (`_retenciones.py:29`), `OperationKind347`/`OperationKind349`
(`_counterpart.py:54`), `ForeignAssetClass` (`_foreign_assets.py:48`) — that the
architecture-boundaries rule says should be declared in `core/`. No behavioral
duplication today (each is used only by aggregation), so this is a placement/authority
nit, not a correctness defect. Batchable with any future `core/` enum-centralization
pass. `aggregation` is also the most cross-domain-reaching application package (imports
iva, transactions, renta, categories, calculations.registry, core) — a god-orchestrator
to watch, by-design today.

### DB-15 (NOTE) — `operator_surface.ModeloLifecycleStep` is the only typed filing-lifecycle vocabulary

The modelo lifecycle (calculate / verify / file / filing-record) is typed only as
`ModeloLifecycleStep` in `application/operator_surface/_models.py:29`; `domain/modelos`
expresses the same vocabulary as prose/string literals. This is genuinely CLI-contract
scoped today, but a domain-side `WorkUnitLifecyclePhase` enum would be the proper
authority. Recorded as a candidate, not a defect.

### Checked-clean inventory (swarm pass, 2026-06-01)

The following packages were probed with the RAG+`rg` tandem and found to match their
claims with no actionable outliers (recorded so future passes do not re-litigate):
`domain/buckets`, `domain/attachments`, `domain/currency`, `domain/deadlines`,
`domain/submission`, `domain/justificante`, `domain/categories`,
`domain/usage_ratios`, `domain/fincas`, `domain/manuals`, `domain/portals`,
`domain/filing`, `domain/renta`, and `domain/calculations` (self-contained authority —
no logic belonging to it is implemented elsewhere; its issue is DB-21 encapsulation,
not misplacement). Among the application packages, `application/ledger`,
`application/evidence`, `application/export`, and `application/inventory` are clean
orchestration (inventory correctly delegates valuation to `domain/profile/inventory`
via an input-DTO pattern); `application/overview` is largely clean (a 900-line
`__init__` doing model-defs + builders is a cohesion nit, `_IVA_REGIME_MODELOS` is an
acknowledged domain-coverage workaround — both NOTE-level, no behavioral
re-implementation).

## Hexagonal edge axis

The second axis of this audit treats the layer boundaries themselves as the unit of
inspection. Every cross-layer import is an edge; an edge that points the wrong way is a
finding. This axis is exhaustive by construction: it is a whole-tree `rg` of
cross-layer imports (relative and absolute), classified module-level (runtime) vs
deferred (TYPE_CHECKING / function-local), so coverage does not depend on which
packages a swarm happened to probe.

**Codified edge contract (the legal dependency direction).** Layers, innermost to
outermost: `core` → `domain` → `application` → `adapters` / `entrypoints`. A lower
layer must never import a higher one. The legal edges are: `domain → core`;
`application → domain, core`; `adapters → application, domain, core`;
`entrypoints → adapters, application, core`. Everything else is an inverted edge.
Domain defines repository **ports** (`_protocols.py` exists in `buckets`,
`attachments`, `modelos`, `filing`, `invoices`, `currency`, `deadlines`); adapters
should implement them. Persistence concretions (`adapters.persistence.storage`:
`SecureObjectRepository`, `Envelope`, `SensitivityClass`, `SecureBoundRepository`)
belong below or beside the consumer, never above it.

**Whole-tree edge inventory (production code, 2026-06-01, `rg`-measured):**

- `adapters → entrypoints`: **0**. Clean.
- `core → application`: **1 site** (`core/resources/_repos/topics.py`, deferred) — see DB-07.
- `core → domain`: a **cluster** of ~11 deferred loaders under `core/resources/_repos/`
  (`user_profile`, `deadlines`, `iva`, `calculations.registry`, `manuals`,
  `categories`, `normatives`, `auth`, `legal_parameters`, `holiday_calendars`,
  `iva_catalogues`) — see DB-18.
- `domain → adapters`: **6 module-level (runtime)** across 3 files + **100 deferred** — see DB-16.
- `domain → application`: **1 site** (`domain/profile/_keys.py:141`, deferred) — see DB-17.
- `application → adapters`: **111 module-level** + 54 deferred — see DB-19.

**Meta-pattern:** the two structural inversions (`core → domain`, `domain → adapters`)
are overwhelmingly expressed as *deferred* imports (TYPE_CHECKING blocks and
function-local imports) — a deliberate cycle-avoidance technique that is itself
evidence the team knows these edges point the wrong way. The deferred count is not a
clean bill of health; it is debt that has been made invisible to the import graph.

### DB-16 (HIGH cluster) — `domain` repository implementations depend on `adapters.persistence.storage`

**Pathway:** the domain layer owns repository *implementations* (not just ports) that
reach down into adapter persistence concretions.

`rg` finds 6 module-level (runtime) `domain → adapters` imports concentrated in three
files — `domain/justificante/_repository.py:24-25`, `domain/submission/_repository.py:14-15`,
`domain/filing/_repository.py:14-15` — each importing `SensitivityClass` and
`SecureBoundRepository` from `adapters.persistence.storage` at module scope. A further
100 `domain → adapters` imports exist as deferred (TYPE_CHECKING / function-local)
references across the repository implementations in `modelos` (×5 repos), `fincas`,
`transactions`, `invoices`, `buckets`, `usage_ratios`, `filing`, and `submission`.

The domain already declares ports (`_protocols.py`), so the intended hexagonal shape
exists — but the concrete `_repository.py`/`_service.py` implementations co-located in
`domain/` bind to the adapter persistence layer rather than living in
`adapters/persistence` behind those ports. The 3 module-level files are the sharp edge
(a true runtime domain→adapter dependency, visible in the import graph and capable of
seeding cycles); the 100 deferred imports are managed debt.

**Disposition:** this is an architectural-intent question, not a mechanical defect.
Either (a) the domain repository implementations should move to
`adapters/persistence/<domain>` behind the existing `_protocols.py` ports, or (b) the
codebase has deliberately chosen domain-co-located encrypted repositories and should
record that as an accepted deviation in an ADR. Recorded HIGH because it touches the
central hexagonal contract and the 3 runtime files are unambiguous. AUDIT-ONLY; needs
an ADR ruling before any relocation. Priority: convert the 3 module-level imports to
deferred at minimum (cheap, removes the runtime edge) pending the larger decision.

### DB-17 (MEDIUM) — `domain/profile/_keys.py` imports `application.wizard` (worst-direction edge)

**Pathway:** domain importing application — the single most inverted edge in the tree.

`domain/profile/_keys.py:141` does `from ...application.wizard._compiler import
compile_profile_keys` (function-local/deferred). It is the *only* `domain → application`
edge in production code. Even deferred, a domain module depending on an application
orchestrator is a direct contract inversion. It compounds DB-01 (the `profile` package
is already a mis-homed catch-all): the profile-keys surface reaches up into the wizard
compiler instead of the wizard depending down on a domain key contract.

**Remediation (audit-only):** invert the dependency — define the key-compilation
contract in domain (or move `compile_profile_keys`' domain-shaped logic down) and have
`application/wizard` depend on it. Fold into DB-01's relocation decision since both
concern the `profile` package's true home.

### DB-18 (MEDIUM cluster) — `core/resources/_repos` inverts `core → domain`/`application`

**Pathway:** the innermost layer (`core`) hosts a resource-repository facade that
lazily imports loaders from `domain` (and once from `application`).

`core/resources/_repos/*.py` contains ~11 deferred imports of `domain.*` loaders
(`load_user_profile_schema`, `load_recargo_bands`, `load_iva_rate_table`,
`ValidatedRegistryAuthority`, `load_manual`, `resolve_category_profiles`,
`load_catalogue` for normatives, `load_default_catalogue` for apoderamientos, etc.)
plus the single `application.topics` import (DB-07). `core` is the innermost layer;
depending on `domain`/`application` even lazily is an inversion. The deferral via
TYPE_CHECKING/function-local is the same cycle-avoidance tell as DB-16.

**Disposition:** `core/resources/_repos` is a registry-facade that arguably belongs in
`domain` (it wraps domain loaders) or should depend only on protocols defined in
`core`. The `application.topics` edge (DB-07) is the most clearly wrong and should move
first. The broader `core → domain` cluster needs the same ADR ruling as DB-16 — is
`core/resources` a legitimate shared-kernel registry, or misplaced one layer too low?
AUDIT-ONLY.

### DB-19 (NOTE / needs ADR) — `application → adapters` is a pervasive direct-concretion dependency

**Pathway:** the de-facto architecture, recorded for an explicit ruling rather than
flagged as a defect.

There are **111 module-level** `application → adapters` imports (plus 54 deferred),
overwhelmingly `adapters.persistence.storage` (encrypted-storage infrastructure) and
`adapters.outbound.aeat.*` / `adapters.inbound.*`. At this scale and runtime-directness,
this is clearly the intended composition pattern: `application` is the layer that wires
adapter concretions. A strict hexagonal reading would route these through ports, but
that is an architecture decision, not a drift to be swept. Recorded as the dominant
structural fact of the application layer so a future ADR can either bless it (declare
`adapters.persistence.storage` an accepted infrastructure dependency) or scope a
ports-based refactor. NOT actionable as individual findings; do not file 111 tickets.

### DB-20 (HIGH) — IVA compensation (Modelo 303) is a domain concept with no domain package

**Pathway:** an entire body of regulatory calculation logic lives in the application
and adapter layers because no domain home was ever created for it.

The Modelo 303 IVA-compensation surface — FIFO carry-forward lot allocation, the
four-year compensation window (LIVA art. 99.5), the wallet-vs-recurrence-vs-override
divergence decision tree, the casilla-component extraction mapping (`69`/`87`/`78`/`110`),
and the `iva.compensacion-disponible-fin-periodo` derivation rule — is implemented
entirely outside `domain/`. `rg` for this logic in `domain/` returns only `fincas`
carry-forward (a different, unrelated rental concept). The regulatory code lives in
`application/calculations/_iva_compensation_history.py`,
`application/calculations/_iva_wallet_reconciliation.py`,
`application/calculations/_iva_wallet_balance.py`, and `application/live/__init__.py`,
with business invariants enforced as pydantic `model_validator`s on application DTOs
(`IvaCompensationCarryForwardLot`, `IvaCompensationReconciliationDecision`).

The derivation rule `posterior + max(0, -resultado)` for the
`iva.compensacion-disponible-fin-periodo` casilla is **duplicated verbatim** across two
non-domain layers — `adapters/outbound/aeat/sede/_declarations.py:1599`
(`_with_derived_303_compensation_available_observation`, operating on raw string
casillas) and `application/live/__init__.py:1131` (`_with_derived_303_compensation_available`,
operating on Decimal `casilla_values` and building a provenance-annotated
`CasillaObservation`). Neither delegates to the other; a registry change to this
casilla's formula requires synchronized edits in both. Confirmed by `rg`.

**Data at risk:** a regulated, BOE/LIVA-grounded calculation surface sits in the
orchestration layer with no single authority; the duplicated derivation is a live
drift hazard; the four-year-window and FIFO rules carry legal grounding that the
calculation-grounding rule wants anchored in a domain authority, not an app helper.

**Remediation (audit-only):** create a `domain/iva_compensation/` (or fold into
`domain/iva`) package owning the carry-forward algorithm, the four-year window rule,
the divergence decision tree, the casilla-component mapping, and the 303 derivation —
returning typed `CasillaObservation`s with provenance. Have `application/calculations`,
`application/live`, and `adapters/sede` all delegate to it; delete the duplicate. This
is the largest single structural finding of the audit; sequence it as its own
ADR-backed campaign. Marquee item.

### DB-21 (HIGH) — `domain/calculations/registry` public surface is systematically bypassed

**Pathway:** a declared public boundary (`registry/__init__.__all__`) that consumers
route around via private-submodule imports.

The registry id type aliases (`CasillaId`, `BindingId`, `RevisionId`, `FormulaId`,
`ParameterId`, `RelationId`, `LegalRefId`, `SourceRefId`, `ExtractionProfileId`, …) live
in `registry/_ids.py` and are **absent from** `registry/__init__.__all__` (verified —
no `_ids` re-export in the package init). Same for `DecimalValue` (`_schema.py`) and
`CounterpartSourceKind` (`_bindings.py`). As a result **33 external modules**
(`from`-anchored, verified 2026-06-01) — across `application/*`,
`domain/{filing,modelos,user_profile,fincas}`, `entrypoints/cli/*`,
`adapters/outbound/google`, and `diagnostics` — import registry *private* submodules
(`._ids`, `._schema`, `._bindings`, `._authority`, `._loader`, `._formula_runtime`,
`._errors`, `._queries`) directly. (CORRECTION: an earlier `rg -l` pass reported 38;
that count included docstring/comment `:class:` cross-references — notably
`core/_tax_domain.py`, which imports only `StrEnum` and is clean. The true
`from`-anchored import count is 33; `core/_tax_domain.py` is NOT a DB-21 site.) Some symbols (`CasillaObservation`,
`ValidatedRegistryAuthority`, `load_legal_parameters_only`) ARE in `__all__` yet are
still imported via their private path.

**Data at risk:** the registry-authority-flow rule makes `registry/__init__` the
contract; 38 private-path couplings mean any internal refactor of the registry
silently breaks consumers across every layer, and the encapsulation the rule mandates
is not real. This is the structural root cause behind several smaller observations.

**Remediation (audit-only):** promote the `_ids` aliases, `DecimalValue`, and
`CounterpartSourceKind` into `registry/__init__.__all__`, then sweep all 38 sites onto
the public import. The `_ids` promotion alone resolves the largest share. Two
domain-sibling cycle-forced `_loader` imports (`iva/_recargo_equivalencia`,
`fincas/_imputacion_parameters`) and the `application/live` `._authority` import are
path-hygiene sub-cases of the same finding — redirect to the public surface (the
symbols are already exported), keeping the imports deferred where cycle-avoidance
requires it.

### DB-22 (MEDIUM) — `application/verification` encodes registry-derived classification policy

**Pathway:** policy logic that interprets registry data implemented in the application
layer instead of beside the registry data it interprets.

`application/verification/_verify.py` owns two rules that read registry
`VerificationExpectation` data and apply policy: `_classify_discrepancy` (`:239`) — the
four-way discrepancy taxonomy with the hard-coded `abs_delta < 10 * tolerance` rounding
threshold and the CORRECTNESS_DIVERGENCE-blocks rule — and `_verification_policy`
(`:183`) — the multi-expectation merge (`min(tolerance)`, `max(min_coverage)`). The
status taxonomy types (`DiscrepancyCause`, `VerificationStatus`) have no domain
counterpart. Authority flow itself is clean (goes through `ValidatedRegistryAuthority`).

**Remediation (audit-only):** move the classification policy and the expectation-merge
rule into `domain/calculations/registry` beside `VerificationExpectation`; leave the
operator-surface DTOs in the application layer.

### DB-23 (LOW) — `application/review.LedgerReviewIssue` duplicates `application/transactions.LedgerImportDiagnosticKind`

`application/review/_filter.py:155` defines `LedgerReviewIssue(StrEnum)` with values
identical to `application/transactions/_diagnostics.py:35` `LedgerImportDiagnosticKind`
(`original-file`, `gap`, `duplicate`, `parser`) — and its own docstring states it
"Mirrors" the other. Substitutability passes (identical shape). **Remediation:** replace
with a re-export/import of `LedgerImportDiagnosticKind`; delete the duplicate. The other
review filter enums (`ReviewItemKind`, `ReviewSeverity`, `ReviewState`, `ReviewFormat`)
are review-surface-only and correctly homed.

### DB-24 (LOW) — `application/registry.RegistryManualId` is a constraint-narrowing duplicate of `ManualId`

`application/registry/_corpus.py:52` redeclares `RegistryManualId(StrEnum)` as a
two-member subset (`renta`, `iva`) of `domain/manuals/_ids.py:12` `ManualId`
(`renta`, `iva`, `sociedades`), with a `_domain_manual_id()` shim converting back.
Because the domain type has an *extra* member, this is a constraint-narrowing
DIVERGENCE, not a transparent shadow — but the narrowing should be expressed as a
`Literal["renta","iva"]` parameter or a named application gate over the canonical
`ManualId`, not a second StrEnum. **Remediation (audit-only):** replace the duplicate
enum with a Literal/gate.

### DB-25 (LOW) — calc-sheets re-decodes registry rounding-code and parameter-temporal vocabulary

`application/storage/calc_sheets/_engine.py` re-parses the registry rounding-code
vocabulary (`"money-2"`, `"integer"`) in `_rounding_rule_for`/`_wrap_rounded` (`:52`)
and re-implements dated-parameter selection in `_resolve_scalar` (`:295`), both of which
the domain `_formula_runtime.py` already owns (`_apply_rounding`, `_resolve_parameter`).
These are parallel *decodings* with divergent output types (Sheets formula string vs
`Decimal`), so they cannot be merged directly — the `translate_formula` AST-walker is
healthy by-design (string co-domain). **Remediation (audit-only):** lift the rounding-code
set to a domain `StrEnum` so both paths share one typed vocabulary; otherwise leave the
divergent evaluators. LOW.

### DB-01 reconciliation (renta↔profile, swarm input)

The R8 renta auditor reached a partially dissenting read on DB-01 worth recording: the
coupling is one-way (`profile → renta`-codes; `domain/renta` does **not** import
`domain/profile`), and the `Renta*`-prefixed records in `profile` describe taxpayer
*facts* (which a profile package may legitimately own) rather than renta *calculations*.
Under that read, the true defect in DB-01 is narrower than "family facts belong in
renta": it is (a) the package **name/claim** ("tax-residence profile") not matching its
three-concern contents, (b) the `Renta*` naming on records that are really taxpayer
facts, and (c) the inventory/amortization error family that has no profile relationship
at all. DB-01 stays open at MEDIUM, but the home decision should weigh this: renaming
the package and relocating the inventory errors may resolve most of it without moving
the family facts into `renta`. The single `domain/profile → application.wizard` edge
(DB-17) remains a clear violation regardless.

### DB-26 (MEDIUM cluster) — application-result ↔ entrypoint-payload twin DTOs share names

**Pathway:** the same result type is declared twice — once in `application` (as
`BaseModel`), once in `entrypoints/cli` (as `OutputSchema`) — under the identical class
name.

A whole-tree duplicate-class-name scan (only 12 collision groups exist in 1700 files —
the codebase is otherwise disciplined) shows the dominant pattern is application/CLI
result twins sharing a name: `AuthLoginResult`, `AuthConfigureResult`, `AuthStatusResult`,
`AuthTestResult`, `AuthClearResult`, `LedgerImportResult`, `LedgerExportResult`,
`ModeloExportResult`, `CensoApplyResult`, `InventoryValuationPreviewResult` — each
defined in both `application/<pkg>` and `entrypoints/cli/*_payloads.py`. Example:
`AuthLoginResult` is a `BaseModel` at `application/auth/_operator.py:162` and an
`OutputSchema` at `entrypoints/cli/_config_payloads.py:294`. This is the same
serialization-chain smell flagged for `IvaCompensationHistoryRow` (DB-20 family): the
CLI re-declares the application result as a wire-contract payload and hand-fans the
fields across.

**Disposition:** partially legitimate — `OutputSchema` is the CLI JSON-contract base, so
a boundary type distinct from the application result is defensible. The actionable
smells are (a) the *identical class name* across layers (a navigability/confusion
hazard — two different types that look like one), and (b) field-for-field hand-copying
that drifts. PER-PAIR field-identity not yet confirmed (the twins differ by base class;
whether fields are 1:1 needs a read of each pair). **Remediation (audit-only):** decide
one pattern — either the application result IS the `OutputSchema` (single type), or the
CLI payload derives from the application result programmatically; at minimum rename so
the two layers don't share a class name. Recorded MEDIUM as a cluster, not 10 tickets.

### DB-27 (NOTE) — `PortalRow` name collision across `adapters` (ORM) and `application` (DTO)

`PortalRow` is a SQLAlchemy `Base` table-row at
`adapters/persistence/storage/sql/_orm.py:52` and an operator-facing `BaseModel`
projection at `application/portals/_service.py:30`. Different layers, different bases,
different purpose — NOT a duplication (substitutability excludes it), but the shared
name is a navigability nit. **Disposition:** rename the application projection (e.g.
`PortalListRow`) if convenient; otherwise leave. NOTE.

### DB-28 (MEDIUM) — `core/` shared kernel holds domain-shaped concerns and a core↔domain cycle

**Pathway:** the innermost layer hosts setup/profile/tax-taxonomy concerns and reaches
back up into `domain`, broken only by type-erased lazy accessors.

`core/` is meant to be the shared kernel, but it carries domain-shaped modules:
`core/profile.py`, `core/profile_catalogue.py`, `core/_tax_domain.py`,
`core/aggregation.py`, and an empty `core/classification/` namespace.

- `core/profile.py` is **misnamed**: its docstring declares it the *"Canonical
  typed-answer model and projection registry for the setup flow"* (`SetupAnswers`,
  `register_project_answers`, `get_project_answers`) — it is a setup/wizard concern, not
  a tax-residence profile. Worse, it depends on `domain` (`domain.deadlines._models`,
  `domain.profile`, the CCAA enum) through lazy accessor functions `_m()`/`_p()`/`_ccaa()`
  that return `Any` with explicit `ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE` comments to
  dodge a circular import. This is simultaneously (i) a `core → domain` inversion
  (DB-18 family), (ii) a type-erasure escape (`Any` returns, flagged as boundary leaks
  by the calculation-grounding rule), and (iii) another node in the profile sprawl —
  bringing the "profile" surface to ~6 sites (`domain/profile`, `domain/user_profile`,
  `application/user_profile`, `core/profile.py`, `core/profile_catalogue.py`, plus the
  registry `source="profile"` bindings) per DB-01.
- `core/_tax_domain.py` is a closed tax-taxonomy enum that also imports the registry
  (one of DB-21's 38 private-path sites; a `core → domain` edge per DB-18). As a closed
  value set in `core`, the enum's *placement* is defensible per the architecture rule;
  its *import of the registry* is the inversion.
- `core/aggregation.py` (`AggregationSourceKind`) is correctly a core closed-value set
  (it is the canonical home DB-10 points operator_surface back to). Not a defect.
- `core/classification/` is an empty namespace package (`__init__.py` only) — a NOTE-level
  stub to either populate or remove.

**Remediation (audit-only):** rename `core/profile.py` to its true subject (setup
answers) and resolve its `core → domain` cycle as part of the DB-18/persistence-boundary
ADR (R5); fold the profile-naming question into DB-01's home decision. The `Any` lazy
accessors should be re-typed once the cycle is broken.

### DB-29 (MEDIUM) — inbound adapter re-export shims violate the no-shim rule

`adapters/inbound/pdf/_errors.py` is a one-file shim re-exporting `PdfModeloImportError`
from its canonical home `domain/justificante/_errors`, so `borrador/_errors.py:13` and
`declaracion/_errors.py:15` import it via `..pdf._errors` rather than from domain.
`adapters/inbound/identity/__init__.py` is a dead shim re-exporting
`core.identity.validate_spanish_tax_id` with **zero** live callers (its only would-be
consumer, `sanitizer/_records.py:18`, already imports from `core.identity` directly).
The architecture-boundaries rule forbids shims/compat layers — move callers to the
canonical path. **Remediation (audit-only):** point `borrador`/`declaracion` at
`domain/justificante/_errors` and delete `pdf/_errors.py`; delete the dead `identity/`
package. MEDIUM (no-shim rule, low risk).

### DB-30 (LOW) — duplicate Spanish-decimal parser in inbound

`adapters/inbound/justificante/_extract.py:213` `_parse_decimal` re-implements the
Spanish-decimal parse (`1.234,56` ↔ `1234.56`) that
`adapters/inbound/pdf/_label_regex.py:64` `parse_spanish_decimal` already owns —
algorithmically identical blocks. Substitutability is blocked only by the error
contract (`_parse_decimal` raises `JustificanteParseError`; `parse_spanish_decimal`
returns `None`). **Remediation (audit-only):** unify under one helper (candidate
`core/decimal`) parameterized on the failure mode; both callers delegate. LOW.

### DB-31 (MEDIUM) — outbound adapters pull application/private internals for runtime context

**Pathway:** driven adapters reach *up into* application (and into private modules) to
resolve context instead of receiving it injected.

`adapters→application` is a legal dependency direction, so this is not a layer
inversion — but the pattern is a coupling/encapsulation smell: outbound adapters import
application internals (mostly deferred) to resolve the active bucket / profile.
`adapters/outbound/aeat/auth/_authenticator.py:1175`, `_clave_movil.py:752,864`,
`sede/_declarations.py:378`, `browser/_factory.py:111` import
`application.workflow._models.{resolve,require}_active_bucket_id`;
`google/_oauth_flow.py:74` imports `application.user_profile._orchestration`
(`build_lifecycle_service`, `fact_value`). Additionally
`google/_calc_sheets_pull.py:55` imports the **private** `_registry_sha` from
`application.storage.calc_sheets._engine`, and `compute_from_pull` (`:841`) invokes the
domain engine `calculate_registry_snapshot` directly inside the adapter.

**Remediation (audit-only):** inject `bucket_id` / profile context into the adapter call
sites rather than having adapters pull it; promote `_registry_sha` to a public surface
if the adapter is a sanctioned consumer; consider an application facade for the
pull→inputs→engine step so the Sheets adapter does translation only. MEDIUM.

### DB-32 (HIGH) — persistence adapter runs a domain calculation in the write path

**Pathway:** storage infrastructure executes a tax-accounting algorithm as a save guard.

`adapters/persistence/profile/inventory.py:207` (`InventoryLedgerRepository.record_movement`)
calls `compute_inventory_valuation(updated)` — a pure domain calculation defined at
`domain/profile/inventory/__init__.py:323` that dispatches FIFO / weighted-average stock
accounting — to validate post-movement state before persisting. RAG+`rg` tandem
confirms: the inventory-valuation cluster is owned by `domain/profile/inventory`
(`compute_inventory_valuation` 0.87, weighted-average 0.61, FIFO 0.49) and the
persistence adapter sits in that same cluster as a consumer. Storage must not run
domain calculations; this is the canonical domain-logic-in-adapter anti-pattern.

**Remediation (audit-only):** move the valuation guard up to the application service
that orchestrates `record_movement`; the persistence adapter accepts a pre-validated
domain object. HIGH.

### DB-33 (MEDIUM) — `assets.py` hardcodes storage namespace literals instead of the registry constants

`adapters/persistence/profile/assets.py:32-33` declares
`_ASSETS_NAMESPACE = "aeat.persistence.profile.assets"` and
`_AMORTIZACION_NAMESPACE = "...assets.amortization"` as raw literals, duplicating
`PROFILE_ASSETS_LEDGER_NAMESPACE.namespace` / `PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE.namespace`
in `storage/_namespace_registry.py:245,255`. The sibling `inventory.py:30` does it
correctly (`_INVENTORY_NAMESPACE = PROFILE_INVENTORY_LEDGER_NAMESPACE.namespace`). The
literals currently match, so no live breakage — but a registry rename silently diverges
the assets repository onto a wrong namespace key (data-loss hazard). **Remediation
(audit-only):** read both from the registry constants like `inventory.py`. MEDIUM.

### DB-20 corroboration & adapters positive space (wave 4)

The outbound auditor independently confirmed and **bounded** DB-20: the Modelo-303
derivation `posterior + max(0, -resultado)` at `adapters/outbound/aeat/sede/_declarations.py:1599`
(`source_locator="formula:87+max(0,-69)"`) is the *only* regulatory derivation in the
outbound layer — no second such formula exists there. Live-write safety is **CLEAN**:
`adapters/outbound/aeat/export/_submitters/__init__.py` is an intentionally empty package
whose docstring permanently forbids submission; no ungated AEAT write path was found;
`AEAT_LIVE_TESTS_ENABLED` appears only in live test files. Shadow-model review of the
adapter layer was clean — notably `sede ObservedCasillaValue` (`value: str` + confidence/
source) is correctly NOT a duplicate of domain `CasillaObservation` (`value: Decimal` +
formula provenance); divergent shapes, distinct roles.

### DB-34 (HIGH) — regulatory tax formulas implemented in CLI handlers

**Pathway:** statutory calculation logic defined in the entrypoint layer.

`entrypoints/cli/_modelo.py` defines two full regulatory formulas:
`_compute_dt12_reduccion_plan_pensiones` (`:2612`) implements the LIRPF DT 12ª 40%
reducción for plan-de-pensiones capital rescate (`pre_2007/totales * gross * 40%`), and
`_compute_sal_reserva_especial_dotacion` (`:2679`) implements the Ley 44/2015 art. 14
SAL/SLL reserva especial (`min(beneficio_neto*10%, max(0, capital_social*50% -
reserva_dotada))`). Both carry Decimal arithmetic, rounding, and statutory guards. The
RAG+`rg` tandem confirms these cluster only at `cli/_modelo.py` (0.55 / 0.48, no domain
module in the cluster) — there is no domain home. The established precedent is the
opposite: `domain/profile/_deduccion_maternidad.py` keeps the Art. 81 LIRPF formula in
domain and the CLI calls it.

**Data at risk:** regulated formulas in an entrypoint cannot be unit-tested without a
CLI harness, are invisible to non-CLI consumers, and violate the calculation-grounding
discipline (legal formulas belong in a grounded domain home). **Remediation
(audit-only):** move both into a domain module (candidate `domain/modelos/` or
`domain/renta/`) with oracle-grounded tests; the CLI calls them. Related references to
these concepts already exist in `application/modelo/_actions.py` and
`domain/deadlines/_models.py` — site the formulas near those. HIGH.

### DB-35 (HIGH) — statutory validation rules enforced only at the CLI boundary

`entrypoints/cli/_modelo.py` defines `_validate_m184_share_sum` (`:940`, Modelo 184:
miembro porcentaje shares must sum to exactly 100%) and `_validate_m347_threshold`
(`:966`, RD 1065/2007 art. 31.1: each M347 contraparte importe must exceed €3,005.06).
These statutory rules operate on typed domain records (`Modelo184MemberRow`,
`Modelo347ContraparteRow`) but live only in the CLI; no domain/application counterpart
exists. Any non-CLI consumer of those records bypasses the rule.

**Remediation (audit-only):** move the rules onto the domain record `model_validator`s
or a domain validation service, so they bind at construction regardless of caller. The
M347 threshold itself is sourced correctly from `core.external_constants` (but see
DB-38 on where that constant lives). HIGH.

### DB-36 (MEDIUM) — CLI handlers bypass the application layer to call domain directly

Several CLI handlers reach past the application layer into domain services:
`entrypoints/cli/_common.py:312` (`_aggregate_renta_filing_inputs`) calls
`resolve_ledger_renta_expense_aggregation_binding_values` from
`domain.calculations.registry` and assembles binding values inline, replicating
`application/aggregation/_modelo_bindings.py:310`
(`resolve_modelo_ledger_binding_values_from_repositories`) which already orchestrates
this with typed output. `entrypoints/cli/_ledger.py` `ratios_set`/`ratios_unset`
(`:2281`,`:2332`) call `load_usage_ratios`/`save_usage_ratios` from `domain.usage_ratios`
directly (no application wrapper exists for the mutating verbs — a real gap, the
read-only `application/ledger/_ratios.py` covers only `eligible`/`validate`). Read-only
`domain.portals` lookups from `_app_live.py:1045,1084` are the benign end of the same
pattern (static registry, no app service).

**Remediation (audit-only):** route `_common.py` aggregation through the existing
application service; add application wrappers for the usage-ratio mutating verbs so the
CLI stops mutating domain persistence directly. MEDIUM (the read-only portals case is
NOTE).

### DB-37 (MEDIUM) — CLI enum-typing + private-import gaps

`entrypoints/cli/_app_live.py:1029` types the `--category` option as `str | None` and
manually coerces `PortalCategory(category)` at `:1051`, so click renders no `Choice` —
violating the architecture rule that closed-enum Typer args declare the enum type. And
`entrypoints/cli/_errors.py:55` imports the private `StoredProfileDriftError` from
`domain.user_profile._errors` (no public re-export through `application.user_profile`).
**Remediation (audit-only):** type `--category` as `PortalCategory`; expose the error
through the application public surface. MEDIUM (the private-import sub-case is LOW).

### DB-38 (MEDIUM) — regulatory thresholds parked in `core/external_constants.py`

`core/external_constants.py:350-356` declares `M347_THRESHOLD_EUR = Decimal("3005.06")`
(RD 1065/2007 art. 31.1) and `MODELO_720_REPORTING_THRESHOLD_EUR = Decimal("50000.00")`
— regulatory filing-obligation thresholds — inside a file otherwise holding AEAT
service URLs / OAuth scopes / MIME types. These are tax-law constants, not technical
infra config; they belong in the registry or a domain constants home. Consumers:
`application/aggregation/_foreign_assets.py:159`, `_counterpart.py:317`,
`domain/modelos/_row_models.py:35`, `entrypoints/cli/_modelo.py:976`. **Remediation
(audit-only):** relocate to the registry (year-keyable) or a domain constants module;
batch with DB-14 (regulatory enums) as a "regulatory values belong in
registry/domain, not core/infra" sweep. MEDIUM.

### DB-39 (MEDIUM) — `core/profile_catalogue.py` is a second core→application registration-slot coupling

Extends DB-28. `core/profile_catalogue.py` uses the same registration-slot pattern as
`core/profile.py`: it holds a runtime reference to application wizard-flow descriptors
(`WizardFlow` from `application/wizard/_catalogue`) behind a `WizardFlowProtocol`, so
`core` carries a live dependency on an application object even though no import is
visible at module load. It is a disguised `core → application` coupling, a second slot
of the DB-28 pattern not covered by that finding. **Remediation (audit-only):** resolve
with DB-28/R5 — the setup/wizard registration slots should live in application or
domain, not core.

### DB-40 (LOW cluster) — borderline domain knowledge in `core/`

Three borderline placements, recorded for the architecture ruling, none a clear defect:
`core/identity/_tax_id.py` implements the Spanish AEAT NIF/NIE/CIF checksum (a
Spanish-tax-specific rule, not generic ID validation) — reuse-justified and pure, but a
`domain.identity` home would be cleaner if it did not reintroduce cycles;
`core/config.py` `Settings` carries domain-named fields (`aeat_m210_engine_live`,
`aeat_iva_catalogue_root`, `aeat_deadline_due_soon_days`) — established settings
convention, no runtime cycle, hygiene note as the 100+ field surface grows;
`core/aggregation.py` (`AggregationSourceKind` etc.) is a defensible cross-layer enum
home (prevents a domain→application cycle, per DB-10) — NOTE only. No action beyond
folding into the persistence-boundary/core ADR.

### Wave-5 positive space (CLI + core)

CLI root family is **CLEAN** — only `config` + `app`; the `failed_app` Typer at
`cli/__init__.py:322` is an import-failure fallback shim (single error-printing
callback), not a third command family. CLI enum-typed params are otherwise correct
(`OutputLanguage`, `TransactionDirection`, `BusinessClassification`, `IvaCategory`,
`EUMemberState`, `ExportSerializationFormat`, `OracleEnvironment`); period is correctly
an open-form string, not a closed enum. The `core/` kernel is otherwise clean generic
infrastructure (`decimal`, `money`, `hashing`, `time`, `parsing`, `i18n`, `redaction`,
`json_contract`, `errors`, `observability`, `corpus_manifest`, `paths`, `locks`,
`classification` sensitivity primitives). `core/_tax_domain.py` is a clean closed enum
(see the DB-21 correction).

## Recommendations

Open work queue (ordered, not yet actioned):

- **R1 (feeds DB-01).** Build the full import graph for the "profile" cluster:
  `domain/profile`, `domain/user_profile`, `application/user_profile`,
  `core/profile.py`, and every renta site that reaches into `domain/profile`.
  Decide the canonical home and the true name for the renta family-facts surface.
- **R2 (closes DB-03).** Rewrite the `domain/modelos` package docstring to its
  real surface with core-struct cross-links. Doc-only, single commit.
- **R3 (campaign-wide).** Continue the per-concept RAG+`rg` sweep across the
  remaining domain packages not yet probed: `buckets`, `deadlines`, `categories`,
  `usage_ratios`, `iva`, `fincas`, `submission`, `justificante`, `attachments`,
  `currency`, `manuals`, `normatives`, `portals`, `auth`. Append each as a new
  `DB-NN` finding here.
- **R4 (application layer).** DONE — swarm probed `aggregation`, `ledger`,
  `evidence`, `overview`, `operator_surface`, `wizard`, `workflow`, `topics`,
  `setup`; findings DB-05..DB-15 recorded.

Priority ordering for remediation (when the action policy opens beyond audit-only):

- **P0 — DB-05** (HIGH, dual `declaration_key` divergence): correctness risk;
  smallest blast radius (one package). Single atomic de-duplication + structural
  test. Do first.
- **P1 — DB-07** (core→application inversion) and **DB-06** (period
  re-implementation): both are clean relocations into `core`/`domain` with existing
  consumers already on the canonical path; medium blast radius.
- **P2 — DB-08, DB-09, DB-10, DB-11, DB-12, DB-13**: localized delegation/typing/doc
  fixes. DB-08 is gated on DB-01's profile-home decision.
- **P3 — DB-01** (profile three-concern split): highest blast radius (23+ consumers,
  two outlier surfaces); needs a deliberate relocation plan and peer coordination.
- **Batch — DB-14** with any future `core/` enum-centralization pass. **DB-15**,
  **DB-03**, **DB-04**, **DB-12/DB-13** docstring items batchable as a doc-hygiene
  sweep.

Hexagonal-edge axis (DB-16..DB-19) needs an architectural ruling, not piecemeal fixes:

- **R5 — ADR on the persistence boundary.** DB-16 (domain repos → adapters), DB-18
  (core/resources → domain), and DB-19 (application → adapters) are three faces of one
  question: is `adapters.persistence.storage` an accepted shared-infrastructure
  dependency, or must domain/application route through ports? One ADR should rule on
  all three. Until it lands, the edge findings stay audit-only.
- **R6 — cheap runtime-edge cleanup (pre-ADR, safe).** Convert the 6 module-level
  `domain → adapters` imports (3 repo files, DB-16) to deferred, and move the single
  `application.topics` import out of `core` (DB-07/DB-18). These remove real runtime
  inversions without prejudging the ADR.
- **R7 — DB-17** folds into DB-01's profile-home decision (domain→application edge).
- **R8 — remaining domain sweep.** DONE — `domain/calculations`, `domain/filing`,
  `domain/renta` + `application/{registry,calculations,verification,review,export,
  storage,live,inventory}` swept; findings DB-20..DB-25 + DB-01 reconciliation
  recorded.
- **R9 (DB-20, marquee).** Scope an ADR-backed campaign to create the
  `domain/iva_compensation` home and migrate the carry-forward / four-year-window /
  wallet-reconciliation / 303-derivation logic out of `application/calculations`,
  `application/live`, and `adapters/sede`. Highest-value structural work surfaced.
- **R10 (DB-21).** Promote the registry `_ids` aliases + `DecimalValue` +
  `CounterpartSourceKind` into `registry/__init__.__all__`, then sweep the 38
  private-path importers onto the public surface. Mostly mechanical once the exports
  land; pairs naturally with R6's path-hygiene cleanup.

- **R11 (DB-26).** Decide the application-result vs CLI-payload pattern (single
  `OutputSchema` type, or programmatic derivation) and stop sharing class names across
  the two layers. Cluster fix, ~10 twin groups.
- **R12 (DB-28).** Rename `core/profile.py` (it is setup-answers), retype its `Any`
  lazy accessors once the `core→domain` cycle is broken, fold into R5/DB-01.

- **R13 (DB-32, HIGH).** Move `compute_inventory_valuation` out of the persistence
  write path into the application inventory service; adapter takes a validated object.
- **R14 (DB-29).** Delete the two inbound shims (`pdf/_errors.py`, dead `identity/`);
  repoint callers to canonical homes.
- **R15 (DB-31).** Inject bucket/profile context into outbound adapters instead of
  upward pulls; promote/relocate the `_registry_sha` private access.
- **R16 (DB-33, DB-30).** `assets.py` read namespaces from registry constants; unify
  the duplicate Spanish-decimal parser under `core/decimal`.

- **R17 (DB-34, DB-35, HIGH).** Move the DT12ª / SAL-reserva formulas and the M184/M347
  statutory validations out of `cli/_modelo.py` into grounded domain homes with
  oracle-cited tests; CLI calls them.
- **R18 (DB-36).** Route CLI aggregation through `application/aggregation`; add
  application wrappers for usage-ratio mutating verbs so the CLI stops mutating domain
  persistence directly.
- **R19 (DB-38, with DB-14).** "Regulatory values live in registry/domain, not
  core/infra" sweep: relocate `M347_THRESHOLD_EUR`, `MODELO_720_REPORTING_THRESHOLD_EUR`
  and the aggregation regulatory enums.
- **R20 (DB-37).** Type the `--category` Typer arg as `PortalCategory`; expose
  `StoredProfileDriftError` via the application public surface.

CAMPAIGN COVERAGE: all six layers now swept on at least one axis — `domain` (22 pkgs),
`application` (25 pkgs), `adapters` (inbound/outbound/persistence), `core`,
`entrypoints/cli`, plus the cross-cutting hexagonal-edge and duplicate-class-name axes.
The audit is broad-complete for a first pass (not "done" — see the rolling-checkpoint
discipline). Next-pass candidates: re-sweep after R-series remediations land; deepen the
DB-20 IVA-compensation campaign; and a focused roundtrip-test audit of the persistence
boundaries surfaced here.

Pending findings are not closed until either a structural fix lands with a
roundtrip/structural test or the finding is formally excluded here with a
documented rationale (per the swarm-audit-cadence "no findings rot" rule). All
remediation is currently HELD at audit-only per the active action policy.

## Running log

- 2026-06-01: Doc created. Baseline domain/application inventory captured.
  First tandem RAG+`rg` pass surfaced DB-01 (profile ownership smear, MEDIUM),
  DB-02 (invoices/transactions twin, excluded), DB-03 (modelos docstring drift,
  LOW), DB-04 (pluralization note). R1–R4 queued.
- 2026-06-01: R1 pass-2 on DB-01. Confirmed `domain/profile` is a three-concern
  catch-all (tax-residence — legitimate; renta/Modelo-100 family facts — outlier;
  inventory/asset/amortization errors — outlier), evidenced by class inventory and
  a single shared `_errors.py`. Mapped the 23+ importer graph and two coupling
  hotspots. DB-01 now actionable but blocked on multi-consumer atomic-relocation
  coordination; severity held at MEDIUM. R1 substantially advanced; remaining R1
  work is the renta-vs-profile boundary decision (rename target).
- 2026-06-01: R3+R4 swarm pass. Six parallel discovery agents (RAG+`rg` tandem,
  substitutability pre-filter) covered 14 domain + 9 application packages. 11 domain
  packages and 2 application packages confirmed clean (see checked-clean inventory).
  New findings DB-05 (HIGH, dual `declaration_key`), DB-06/07/08 (MEDIUM:
  period re-impl, topics hex-inversion, wizard SituacionFamiliar re-derive),
  DB-09..DB-13 (LOW-MEDIUM: setup enum, operator_surface SourceKind, iva export
  asymmetry, normatives phantom singleton, auth empty `__init__`), DB-14/15 (NOTE).
  DB-05, dual-`declaration_key` divergence, and the topics inversion were
  independently `rg`-verified by the coordinator before recording; DB-09 fixture
  sub-lead and DB-12 left flagged-unverified. Remediation priority ordering added to
  Recommendations; all work HELD at audit-only.
- 2026-06-01: Hexagonal-edge axis opened. Whole-tree `rg` of cross-layer imports
  (relative+absolute), classified runtime vs deferred. Edge contract codified; full
  edge inventory recorded. Findings DB-16 (HIGH, domain repos→adapters: 6 runtime/100
  deferred), DB-17 (MEDIUM, sole domain→application edge), DB-18 (MEDIUM, core/resources
  →domain cluster), DB-19 (NOTE, application→adapters 111 runtime = de-facto
  architecture needing an ADR). Meta-pattern: structural inversions hidden behind
  deferred imports. R5 (persistence-boundary ADR), R6 (cheap runtime-edge cleanup),
  R7, R8 queued. `adapters → entrypoints` confirmed clean (0).
- 2026-06-01: R8 swarm pass (post-reindex: 110k code chunks fresh). Four agents swept
  the heavy central domains + registry-adjacent application packages. `domain/filing`,
  `domain/renta`, `domain/calculations` confirmed clean of misplacement;
  `application/{export,inventory}` clean. New findings DB-20 (HIGH, marquee — IVA
  compensation is a domain with no domain package; 303 derivation duplicated across
  `application/live` and `adapters/sede`), DB-21 (HIGH — registry public-surface
  bypassed by 38 private-path importers), DB-22 (MEDIUM, verification policy in app),
  DB-23/24/25 (LOW). DB-01 reconciled with the renta auditor's dissent (defect is
  name + `Renta*` prefix + inventory errors, not necessarily moving family facts to
  renta). DB-20 and DB-21 both coordinator-`rg`-verified before recording. R9 (IVA
  compensation domain), R10 (registry export promotion) queued.
- 2026-06-01: RAG temporarily down — pivoted to deterministic rg-only structural
  scans. Whole-tree duplicate-class-name scan (12 collision groups in 1700 files, low
  noise): DB-26 (MEDIUM, application↔entrypoints `*Result`/payload twins sharing
  names, ~10 groups), DB-27 (NOTE, `PortalRow` ORM-vs-DTO name collision). core/
  internals map: DB-28 (MEDIUM, `core/profile.py` misnamed setup-answers + `core→domain`
  cycle via `Any` lazy accessors; profile sprawl now ~6 sites; `core/classification`
  empty stub). CLI root confirmed `config`+`app` (a `failed_app` fallback Typer at
  `cli/__init__.py:322` flagged for verification). R11, R12 queued. Next: rg-only
  adapters-internals swarm.
- 2026-06-01: Adapters-internals swarm (3 agents: inbound, outbound, persistence;
  rg-only during the RAG outage). RAG returned mid-pass; DB-32 re-verified with the
  rag+rg tandem (inventory-valuation cluster owned by `domain/profile/inventory`, the
  adapter is a consumer). New: DB-29 (MEDIUM, inbound shims), DB-30 (LOW, dup decimal
  parser), DB-31 (MEDIUM, outbound pulls application/private internals), DB-32 (HIGH,
  domain calc in persistence write path), DB-33 (MEDIUM, assets namespace hardcode).
  DB-20 corroborated and bounded to one outbound function; live-write safety confirmed
  CLEAN; adapter shadow-models clean. R13–R16 queued. Adapters layer fully swept;
  remaining frontier is `entrypoints/cli` + deeper `core/` internals.
- 2026-06-01: Final-frontier swarm (entrypoints/cli + core internals; rag+rg tandem
  mandated). CLI root confirmed CLEAN (config+app; failed_app is an import-failure
  shim). New: DB-34 (HIGH, regulatory DT12ª/SAL formulas in cli/_modelo.py — RAG-tandem
  confirmed no domain home), DB-35 (HIGH, M184/M347 statutory validation only in CLI),
  DB-36 (MEDIUM, CLI bypasses application for aggregation + ratio mutation), DB-37
  (MEDIUM, CLI enum-typing + private-import gaps), DB-38 (MEDIUM, regulatory thresholds
  in core/external_constants), DB-39 (MEDIUM, core/profile_catalogue 2nd core→app slot,
  extends DB-28), DB-40 (LOW, borderline domain knowledge in core/identity, config,
  aggregation). HONESTY CORRECTION: DB-21's "38" was an `rg -l` over-count including
  docstring `:class:` matches; true `from`-anchored import count is 33, and
  `core/_tax_domain.py` is NOT a DB-21 site (clean StrEnum). core/ kernel otherwise
  clean. R17–R20 queued. All six layers now swept; broad-complete first pass.
- 2026-06-01: EXECUTION begun (policy moved from audit-only to execute per the standing
  goal). Landed: W01.P01 registry publish (28 symbols onto the public surface,
  collection-gated) and W01.P03 S14-S18 (16-file `_ids` repoint, commit 072a57a47).
  Governance triad committed and pushed (5035ca3bd). W01.P02 (the broader
  registry-package-import sweep, 29 files) was executed then BACKED OUT: it exposed
  DB-41 and re-staging by a peer `git add -A` risked committing it broken. Recurring
  maintenance Wave W08 added (ty/pyright, radon/ruff complexity, import-linter triage).
- DB-41 (HIGH, NEW) — latent order-dependent circular import between `domain.invoices`
  and `domain.iva._invoice_classification`. `invoices/__init__.py:11` imports from
  `iva/_invoice_classification`, which at `:62` does `from ..invoices import IvaRate`
  (the package, not the leaf) while `invoices/__init__` only defines `IvaRate` at `:16`
  (after line 11). It works ONLY when `domain.iva` is imported before `domain.invoices`;
  any module that imports the registry package early (registry/_bindings imports
  `domain.invoices`) flips the order and triggers a partially-initialised-module
  ImportError. Robust fix: `iva/_invoice_classification.py:62` should import `IvaRate`
  from the leaf `..invoices._enums` (its definition site) like the adjacent
  `InvoiceValidationError` already does. A peer is mid-edit on both cycle files (both
  `MM`), so this is left to their fix or DB-11. **W01.P02 is BLOCKED on DB-41/DB-11**:
  do not re-run the registry-package-import sweep until the invoices/iva cycle is
  order-independent. Verified by `rg` and a direct `import aeat.domain.invoices`
  traceback.
- 2026-06-02: Execution session 2 (all collection/test-gated, committed + pushed
  individually). Landed: DB-12 (normatives singleton), DB-13 (auth re-export +
  consumer repoint), DB-03 (modelos docstring), DB-05 S67 (declaration_key unified to
  one .upper() definition; 98 workflow tests pass), DB-09 (setup iva_regime typed
  IVARegime with case-fold validator; subsumed S75), DB-23 (LedgerReviewIssue collapsed
  into LedgerImportDiagnosticKind; 184 review tests pass), DB-37 G2 (StoredProfileDriftError
  public import), DB-29 (PdfModeloImportError promoted to justificante public + borrador/
  declaracion repointed + dead identity shim deleted). Two CROSS-AGENT DEFERRALS recorded:
  (a) DB-37 G1 (--category enum typing on entrypoints/cli/_app_live.py) — peer mid-edit
  on that file; (b) DB-29 S41 pdf/_errors.py shim DELETION — HEAD's adapters/inbound/pdf/
  __init__.py still imports it (peer is repointing __init__ to domain.justificante);
  shim restored to keep HEAD buildable, deletion deferred until the peer's __init__
  repoint lands. Pattern reaffirmed: collision-check every file (git status --short)
  before editing; never delete a module whose HEAD importers haven't been repointed yet.
- 2026-06-02 (cont.): three more findings landed, gated + pushed: DB-30 (justificante
  _parse_decimal now delegates to canonical pdf.parse_spanish_decimal; 168 tests),
  DB-08 (wizard verifier uses domain SituacionFamiliar.conjunta_eligible()/
  monoparental_required() instead of re-derived frozensets; 273 tests), DB-27 (ORM
  PortalRow renamed PortalOrmRow to disambiguate from the application DTO; 58 tests).
  Session-2 total: 11 findings closed (DB-03/05-S67/08/09/12/13/23/27/29/30/37-G2).
  Remaining contained candidates: DB-24 (RegistryManualId fold), DB-38 (M347 threshold
  re-export), DB-06 (period re-impl), DB-10 (SourceKind), DB-35 (M347/M184 validators),
  DB-34 (CLI formulas), DB-36 (CLI bypass). W01.P02 + DB-29-S41 deletion + DB-37-G1
  remain blocked on peer-owned files (re-check each pass).

- 2026-06-02: DB-38 dispositioned. The cli/_modelo consumer now imports
  `M347_THRESHOLD_EUR` directly from `core.external_constants` (its true home) — landed.
  The `_row_models`/`modelos` RE-EXPORT removal is EXCLUDED: a peer restored it with the
  explicit `as X  # re-export` idiom and `test_row_models.py` asserts the value, so the
  re-export is intentional and tested, not a dead shim. DB-38 closed as partial-landed +
  excluded-residual; no further action. Collection green (13040).

- DB-42 (MEDIUM, NEW — surfaced by W08.P25 import-linter triage) — the `.importlinter`
  layered-architecture gate is currently NON-FUNCTIONAL on this branch: it runs with
  `unmatched_ignore_imports_alerting = error` and `exclude_type_checking_imports = True`,
  and exits 1 before evaluating any contract because the `ignore_imports` lists have
  accumulated stale / path-mismatched entries (it errors on the first unmatched ignore).
  Investigation (grimp graph built with `exclude_type_checking_imports=True` to match
  the config) found ~93 unmatched ignore lines. CRITICAL NUANCE: a naive bulk-removal is
  UNSAFE and was reverted — most "unmatched" ignores still cover *sanctioned* edges whose
  path drifted: (a) production DB-16 deferred `domain.<pkg>._repository -> adapters.
  persistence.storage.*` imports (ADR-pending, legitimately ignored) pinned at a stale
  submodule (`-> storage.sql` vs the live `-> storage.envelope`); (b) test-fixture
  cross-layer imports "permitted per convention" pinned at a moved target (`->
  application.ledger._models` vs the live `-> application.ledger`); (c) the DB-13 repath
  itself (`core.resources._repos.apoderamientos -> domain.auth.apoderamientos` became
  `-> domain.auth`), which silently staled that ignore. Removing these surfaced 36
  violations that were correctly ignored. **Correct reconciliation:** for each unmatched
  ignore, decide truly-gone (remove) vs moved (re-pin at the real edge path), verified
  against the TYPE_CHECKING-excluded grimp graph; do NOT bulk-delete. Best sequenced
  WITH the DB-16/R5 persistence-boundary ADR — once domain repos move behind ports the
  bulk of the domain->adapters ignores disappear entirely rather than needing re-pinning.
  Interim option: set `unmatched_ignore_imports_alerting = warn` so the gate evaluates
  contracts (catching NEW violations) instead of hard-failing on stale pins. Verified by
  repeated `lint-imports` runs + a grimp reconciliation script. Add as W08.P25 follow-up
  Steps; gate is RED until reconciled.

- 2026-06-02 (cont.): three peer-blockers re-checked; two cleared and completed.
  DB-29 S41 COMPLETE — the peer's pdf/__init__ repoint to domain.justificante landed in
  HEAD, so the orphaned pdf/_errors.py shim was deleted (collection 13043). DB-37
  COMPLETE — G1 (`--category` typed PortalCategory so Typer renders Choice; manual
  coercion dropped) once _app_live.py freed, plus G2 earlier. DB-41 PARTIAL FIX —
  _invoice_classification imported IvaRate from the ..invoices package (partial during
  invoices/__init__ load); switched to the ..invoices._enums leaf, fixing the
  invoices-first direction that the W01.P02 registry sweep triggered (332 iva+invoices
  tests pass). The inherent iva<->invoices bidirectional package cycle remains for the
  unusual iva-first-direct path (pre-existing, not hit in collection); full robustness
  needs breaking the bidirectionality (DB-41/DB-11). W01.P02 is now substantially
  de-risked (registry->_bindings->invoices works); a careful full-sweep re-attempt with
  collection gating is the next W01 step.

- 2026-06-02: W01.P02 + P03 S19-S20 LANDED — the DB-21 registry public-surface sweep
  re-attempted after the DB-41 invoices-first cycle fix; 29 modules repointed off private
  registry submodules onto `domain.calculations.registry`, collection clean (13043),
  symbol-verified against `__all__`, `_loader` (cycle-forced) left private. W01 is now
  complete except S21.
- DB-11 / W01.P03.S21 DISPOSITION — RE-SCOPED (not actioned as written). The "export
  asymmetry" (IvaInvoiceClassification defined in `iva/_invoice_classification`, listed
  in that private module's `__all__`, absent from `iva/__init__`, re-exported by
  `invoices/__init__`) is INTENTIONAL cycle-avoidance, not a defect. The class is
  invoice-shaped and consumed only by `invoices`, so `invoices` is its canonical public
  home; it is defined under `iva` only because it needs the iva substrate enums
  (IvaCategory/IvaRateKind/IvaFlowDirection). The literal DB-11 fix (add it to
  `iva/__init__.__all__` + make invoices import from `..iva`) would create a HARD
  bidirectional package cycle (`iva/__init__ -> _invoice_classification -> invoices` and
  `invoices/__init__ -> iva`) — the very cycle DB-41's leaf imports avoid. Correct
  resolution: keep `invoices` as the canonical exporter; the proper structural cleanup
  (relocate the class fully into `invoices`, eliminating the iva->invoices edge) is
  gated on the DB-41 full bidirectional-cycle break and is tracked there. S21 left open
  in the plan, annotated excluded-as-written.
- 2026-06-02: DB-34 + DB-20 marquee LANDED (all collection/test-gated, atomic
  `relocation:`-tagged commits, pushed). DB-34: the DT-12ª LIRPF plan-pensiones
  reducción and Ley 44/2015 art. 14 SAL reserva especial formulas moved from
  `cli/_modelo.py` into `domain/modelos/_dt12_reduccion.py` /
  `_sal_reserva_especial.py` with `PensionReduccionError` relocated to
  `domain/modelos/_errors.py`; oracle + guard tests migrated to
  `domain/modelos/test_fiscal_reductions.py` (W02.P05 S25-S27). DB-20: the
  `domain/iva_compensation/` package created and the IVA-compensation surface
  relocated across W03 — P07 (5 guard errors), P08 S35 (carry-forward models +
  projection + `derive_303_compensation_available`), S36 (reconciliation data
  models + the regulatory decision validator; landed jointly with peer
  `e53b80c95`, consumer sweep completed), S37 (wallet balance projection), P09
  S38 (collapsed the duplicated `posterior + max(0, -resultado)` 303 derivation
  onto the domain function across `application/live` + `adapters/sede`), S40
  (dropped the application-calculations facade re-exports; all callers now import
  from the domain home). **Hexagonal deviation recorded:** the boundary-mapping
  functions that consume adapter/application types — `iva_compensation_period_key`
  (adapter `safe_repository_id`), `iva_compensation_state_from_filed_observation`
  (application port), and `reconcile_iva_compensation_wallet` + its wallet/
  recurrence predicates (adapter `IvaCompensationWalletObservation`) — CANNOT move
  to domain without a `domain->adapters/application` edge; they stay in application
  pending domain observation port-Protocols, tracked as new plan step W03.P08.S89.
  **Peer regression flagged (not in this campaign's scope):** three Modelo 303
  engine tests (`test_bucket_aggregation_flow` resultado-regimen-general, two
  `test_iva_wallet_engine_integration`) red on a peer-#222 303 autoconsumo-promotor
  registry calculation regression (`iva.resultado-regimen-general` resolves to 0 on
  positive input); independent of the behaviour-neutral IVA-compensation relocation
  (verified import-source-only; full collection clean at 13040).

- 2026-06-02: DB-42 RESOLVED + import-linter gate RESTORED (commit `4636bde35`).
  Root cause of the broken gate: `lint-imports` exits 1 *without evaluating any
  contract* because import-linter aborts the whole run on the first
  `ignore_imports` entry that matches no edge — and
  `domain.deadlines._profiles -> application.wizard._catalogue` (resolved in Wave
  3 P04) was still pinned. The hexagonal gate had been blind for as long as that
  ignore was stale. Fix: removed the four confirmed-stale `domain->wizard` ignores
  (verified gone from source; only the function-local `_keys -> _compiler` edge
  remains), and set `unmatched_ignore_imports_alerting = warn` on every contract
  so a future stale entry degrades to a warning instead of blinding the gate.
  With the gate evaluating again, it reports the drift it was hiding — **0 kept,
  4 broken** — decomposed as:
  - **~9 production layer violations.** Seven are domain repositories importing
    adapter persistence (`domain.{usage_ratios._service, justificante._repository,
    buckets._event_repository, transactions._repository, modelos._runtime_repository,
    filing._runtime_repository, filing._repository, submission._repository} ->
    adapters.persistence.storage.*`) — this is **DB-16** (domain-repos→adapters),
    whose durable fix is the persistence-boundary ADR / repository-Protocol
    inversion (R5). One is `core.resources._repos.apoderamientos -> domain.auth`
    (**DB-18**, core→domain). One is `calculations.registry._scenarios ->
    domain.renta` (no-renta contract; the production path is meant to use the
    `CrossDomainSnapshotCheck` Protocol injection — `_scenarios` bypasses it).
  - **~54 test-file edges.** Domain/core test modules importing adapters/application
    for real-adapter roundtrip + fixture setup (sanctioned per the roundtrip
    discipline). Their old ignores went stale when the tests were renamed; they
    need fresh, precisely-pinned ignore entries.
  - **93 stale `ignore_imports`** total (the unmatched warnings) — edges since
    refactored away. Tracked for cleanup.
  Remediation tracked as plan Wave **W09** (P26 clean stale ignores, P27 triage +
  resolve violations cross-referencing DB-16/DB-18, P28 restore strict alerting).

- 2026-06-02 (cont.): import-linter gate driven from 0/4 to **1 kept / 3 broken**
  with the broken signal now isolated to exactly the real drift. core-not-outer is
  GREEN (commit `d690ac919` repointed apoderamientos to its canonical submodule so
  its sanctioned-deferred-loader ignore matches; commit `1990c6d01` re-sanctioned
  29 stale test-file roundtrip/fixture/oracle edges across the three contracts).
  The three still-broken contracts (no-renta, domain-not-application, layered) all
  reduce to **9 production root-cause edges**: eight domain repositories importing
  the secure-storage adapter (`domain.{filing._repository, filing._runtime_repository,
  buckets._event_repository, transactions._repository, usage_ratios._service,
  justificante._repository, submission._repository, modelos._runtime_repository} ->
  adapters.persistence.storage.{envelope,runtime_repository,...}`) — this is DB-16
  (S92) — plus `calculations.registry._scenarios -> domain.renta` (S90; domain-not-
  application and layered also red via indirect chains *through* the DB-16 edges, so
  fixing DB-16 collapses them). DB-16 has two sub-shapes: (a) module-level
  subclassing — `filing/_repository` subclasses the adapter `SecureBoundRepository`
  base; (b) function-local lazy imports inside repo methods (buckets, transactions,
  usage_ratios, the _runtime_repository modules) — structurally identical to the
  resource-management-api ADR's sanctioned core/resources deferred loaders. The
  invert-vs-sanction choice IS the queued **R5 persistence-boundary ADR**; S92 is
  gated on it. A unilateral refactor of the secure-storage base (consumed by every
  typed repository) is high-blast-radius and must be ADR-bound first.

- 2026-06-02 (cont.): **import-linter PRODUCTION hexagonal drift driven to ZERO.**
  Every production layer violation the restored gate surfaced is now resolved:
  - DB-18 `core.resources._repos.apoderamientos -> domain.auth` — fixed by
    repointing to the canonical submodule so the sanctioned deferred-loader ignore
    matches (`d690ac919`); core-not-outer GREEN.
  - DB-16 (8 domain repositories -> adapters.persistence.storage) — verified as the
    secure-persistence-foundation ADR's deliberate per-domain repository pattern,
    NOT drift; sanctioned with ADR-referencing ignores (`31320b726`). S92 closed as
    reconciled-not-inverted (the audit's HIGH grade was a false positive — the base
    SecureBoundRepository is SQL/crypto-coupled and cannot move to core, and the
    persistence ADR deliberately co-locates the repositories with their domain).
  - S90 `calculations.registry._scenarios -> domain.renta` — the production parity
    harness's side-effect renta import (the F7 coupling the no-renta contract
    forbids) relocated to its three test consumers, matching the established M100
    registry-test pattern (`6b3790049`). The production registry is now renta-free.
  All remaining contract red (no-renta, domain-not-application, layered) is
  sanctioned test-infrastructure edges — direct + transitive roundtrip/fixture/
  oracle imports mandated by the roundtrip-discipline rule. Residual W09 work:
  P26 enumerate the full ~50 sanctioned roundtrip-test edges (or a name-scoped
  wildcard), then P28 restore `unmatched_ignore_imports_alerting = error` so the
  gate reds loudly on any NEW drift. The gate's production-drift signal is already
  clean today.

- 2026-06-02 (cont.): **W09 COMPLETE — import-linter hexagonal gate fully GREEN
  (4 kept / 0 broken / exit 0).** From its prior totally-blind aborting state, the
  gate now evaluates and enforces all four contracts. Completion mechanics:
  grimp (the import graph engine) enumerated the exact complete remaining set —
  321 test-source forbidden edges, ZERO production — 251 unique ones appended as
  sanctioned roundtrip/fixture/oracle ignores (roundtrip-discipline rule); the two
  forbidden contracts (no-renta, domain-not-application) scoped to
  allow_indirect_imports = true (they guard DIRECT coupling; the layered contract
  enforces full ordering; production direct coupling is zero); 91 stale unmatched
  ignores pruned (grimp-verified gone). Alerting kept at `warn` (a new violation
  still reds the gate; stale ignores degrade gracefully instead of re-blinding it).
  Net hexagonal-drift outcome for the import-linter surface: every production
  violation fixed (DB-18 apoderamientos, S90 _scenarios) or ADR-reconciled (DB-16
  per the secure-persistence-foundation ADR); the gate now continuously catches any
  NEW production layer drift. Plan W09 (S90-S94) closed.

- 2026-06-02 (cont.): **W08 recurring tooling-triage tick** (post-W09-close cadence).
  - **import-linter (P25)**: GREEN, 4 kept / 0 broken (W09). Closed S88.
  - **ty (P23)**: baseline **918 diagnostics**. Dominated by `invalid-argument-type`
    (730) + `str` (254) ≈ 85% — but sampling shows these are largely ty's
    conservative `**dict` kwargs-unpacking handling in TEST code (one
    `**{"año_override": 2026}` call emits one diagnostic per target parameter,
    a multiplier) plus ty being a newer/stricter checker than the authoritative
    pyright. Low production actionability. The actionable production subset is the
    smaller classes: `unresolved-attribute` (73), `invalid-return-type` (14),
    `not-subscriptable` (14), `missing-argument` (11), `no-matching-overload` (8),
    `unresolved-reference` (3) — triage these incrementally; do NOT chase the
    `**dict`-unpacking test noise. (pyright run deferred to next tick — slower; ty
    + radon captured this tick.)
  - **radon (P24)**: baseline **582 blocks at grade C or worse**; D-and-worse
    production offenders to target for refactor: `_initial_values` (E-35),
    `reconcile_iva_compensation_wallet` (D-22), `calculate_modelo_revision` (D-23),
    `_resolve_m210_rate` (D-26), `_evaluate_m210_resolve_rate` (D-27),
    `verify_declaracion` (D-23), `_apply_iva_compensation_decision_binding` (D-22),
    `RemoteStateGuardPolicy._validate_policy` (D-27), `taxpayer_profile_from_mapping`
    (D-26), `build_revision_validation_context` (D-26); the high-complexity `test_*`
    functions are acceptable (data-table tests). Recorded as DB-43 (code-quality
    tooling baseline) for incremental refactor under the originating waves.
  W08 is standing/recurring — these baselines re-evaluate each cadence tick.

- 2026-06-02 (cont.): **DB-24 / W04.P11.S45 dispositioned EXCLUDED via the
  substitutability pre-filter** (not actioned-as-written). The proposed fold of
  `application.registry._corpus.RegistryManualId` (members {renta, iva}) into the
  domain `ManualId` ({renta, iva, **sociedades**}) fails the pre-filter:
  `ManualId` is a strict SUPERSET, so `RegistryManualId` is a deliberate
  constraint-divergent enum encoding the renta/iva-only *registry manual operator
  surface* (its docstring: "Manual identifiers approved for the registry manual
  operator surface"). A sociedades (IS / modelo-200) manual DOES exist in the
  corpus but is wired through a different path (`_data/registry/aeat/legal/is.toml`
  `corpus_path`), NOT the RegistryManualId operator commands. Folding to `ManualId`
  + a CLI `Choice([renta,iva])` gate would relocate the constraint from the type
  system to a runtime boundary, type-admitting `ManualId.SOCIEDADES` into the
  registry corpus models (`RegistryTopicProjection.manual` et al.) for any non-CLI
  constructor — a net weakening. `_domain_manual_id` (`ManualId(manual_id.value)`)
  is a legitimate operator-surface→domain boundary conversion, not a re-export
  shim. KEEP RegistryManualId; same disposition family as DB-11 / DB-38 / S21
  (constraint-shape divergence, excluded-as-written).

- 2026-06-02 (cont.): **DB-26 / W04.P13 (S49-S52) twin-DTO analysis** (surfaced,
  not yet executed — contract-sensitive, needs careful per-twin work). The CLI
  Auth payloads `AuthStatusResult` / `AuthTestResult` / `AuthLoginResult` in
  `cli/_config_payloads.py` are NOT pure duplicates: they are thin `extra="allow"`
  OutputSchema envelopes that deliberately forward the independently-evolving
  application `AuthStatusResult` (application/auth/_operator.py, with
  `AuthTestResult(AuthStatusResult)` subclassing) without redeclaring
  provider-specific fields — a legitimate CLI-output adapter pattern. The real
  DB-26 smell for these three is the SHARED CLASS NAME across layers (confusing),
  not their existence; the lighter fix is rename-disambiguation (`*Payload`) rather
  than collapse, since "emit the application result directly" would couple the
  application model to the CLI OutputSchema contract. The genuinely actionable
  collapses are the 1:1 cases: `AuthClearResult` (S49, declares removed_sessions/
  cleared_workflow_state/cleared_locks 1:1), `AuthConfigureResult` (S50, nullability
  reconcile), and the Ledger/Modelo/Censo/Inventory projections (S51/S52). Each
  needs per-twin verify-before-action: confirm 1:1 vs adapter, and preserve the CLI
  JSON output contract (user-facing). Deferred to focused execution.

- 2026-06-02 (cont.): **DB-26 / W04.P13 S49+S50 EXECUTED.** The two 1:1 collapses
  landed via the boundary-safe projection pattern (a `from_result` classmethod on the
  CLI payload that projects the application result; CLI→application direction, no
  inversion): `AuthConfigurePayload.from_result(AuthConfigureResult)` plus a
  nullability reconciliation of its seven app-mirroring fields from `X | None = None`
  to the application model's non-nullable `str = ""` / `bool = False` (S50, commits
  `5b6b21593` + `c69a64506`, S50 closed); and `AuthClearPayload.from_result(
  AuthClearResult)` (S49 T5, 1:1, no nullability gap, commit `c3c17e495`). Each was
  verified behaviour-neutral against the 10-test auth surface + 14-test
  json-schema-conformance/common-output gates (output unchanged; the conformance gate
  pins schema registration + envelope round-trip, not per-field nullability, so the
  tightening carried no contract risk). The three pass-throughs T2/T3/T4
  (`AuthStatusPayload`/`AuthTestPayload`/`AuthLoginPayload`) are CONFIRMED
  boundary-correct and NOT collapsed: their `extra="allow"` envelope is the canonical
  CLI adapter over an independently-evolving application model, and "emit the
  application result directly" would require a CLI `@register_schema` decorator on the
  application-layer `BaseModel` — a hexagonal inversion. Their actionable smell (shared
  class name) was already resolved by the earlier `*Result`→`*Payload` rename. S49 is
  therefore complete on its actionable surface (T5 collapsed; T2/T3/T4 dispositioned
  wontfix-boundary-correct); the remaining open W04.P13 work is S51/S52
  (Ledger/Modelo/Censo/Inventory projections).

- 2026-06-02 (cont.): **DB-26 / W04.P13 S52 EXECUTED; S51 PARTIAL.** Applied the same
  boundary-safe rename + `from_result` projection pattern to the remaining twins, each
  verified behaviour-neutral (serialization by field + `@register_schema` string key;
  `model_dump(mode="json")` kept inside each projection to preserve typed-id/enum/
  nested coercion exactly). **S52 complete** (commit `df0a98a12`): CLI
  `CensoApplyResult`→`CensoApplyPayload` with `from_result` (T9), and
  `InventoryValuationPreviewResult`→`InventoryValuationPreviewPayload` with a
  *flattening* `from_result` that lifts the application wrapper's inner `preview`
  fields + `bucket_event_ids` (T10); 201 censo+conformance + 25 inventory tests green.
  **S51 partial** (commit `57ed96989`): CLI `LedgerExportResult`→`LedgerExportPayload`
  (T6, excludes `payload` bytes + appends `output_path`) and
  `LedgerImportResult`→`LedgerImportPayload` (T7, threads the three operator notices);
  25 ledger export/import + conformance tests green. Also fixed two `TYPE_CHECKING`
  relative-import depths (`....`→`...` for the two cli/-level payload modules) surfaced
  by `ty check`; runtime/tests were green regardless since the imports are type-only.

- 2026-06-03: **S51 COMPLETED — T8 (ModeloExport) landed; S51 closed.** CLI
  `ModeloExportResult`→`ModeloExportPayload` with a `from_result` projection that
  stringifies the application `Path` output_path and excludes the fichero-BOE bytes
  (`operation` stays the CLI-only default); the export handler calls `from_result` instead
  of re-declaring the 11-field map (commit `a13133ee5`). Behaviour-neutral:
  `@register_schema("modelo.export")` preserved. Verified in a registration-complete
  context — 18 tests green (`test_modelo_export_verb` end-to-end + 17
  json-schema-conformance / envelope-roundtrip), `ty` clean on the payload module. This
  was attempted on 2026-06-02 but abandoned then due to a concurrent peer edit on
  `_modelo.py`; this turn `_modelo.py` was clean and the diff was confirmed mine-only
  before commit. (The commit moment coincided with a transient peer duplicate-key edit in
  `pyproject.toml` that briefly blocked `uv`; the file self-resolved and the full
  registration-complete run then confirmed green.) S51's three twins (T6 LedgerExport,
  T7 LedgerImport, T8 ModeloExport) are now all collapsed via the projection pattern.

- 2026-06-02 (cont.): **DB-36 / W07.P22 (S82+S83) EXECUTED.** The CLI helper
  `cli/_common.py:_aggregate_renta_filing_inputs` imported the domain function
  `resolve_ledger_renta_expense_aggregation_binding_values` directly — an
  entrypoints→domain edge skipping the application layer. **S82** (commit `fa260b91a`)
  replaces the inline domain orchestration with the application service
  `resolve_modelo_ledger_binding_values_from_repositories(modelo="100",
  revision=snapshot.revision, period="0A")` and drops the domain import. The
  narrow-vs-broad substitutability concern (the service also owns iva + renta-income
  branches) was **resolved by inspection, not assumed**: modelo 100/2025 declares only
  `ledger_renta_expense_aggregation` ledger-binding sources (the other branches are
  gated off by `_revision_has_binding_source`), and
  `aggregation_period_for_modelo(filing_year, "0A")` returns `str(filing_year)` —
  exactly the prior inline period arg — so the resolved `binding_values` are identical
  for modelo 100. **S83** (same commit) removes the application-test→entrypoints
  layering violation (`test_renta_ledger.py:35` imported the private CLI helper); the
  test now drives the application service directly and asserts on the binding-id-keyed
  output. Verified behaviour-equivalent: 12 renta-ledger + 23 backend-boundary tests
  green; `ty` clean. The one combined-run failure was the registry loader-cache race
  the `aeat-local-execution` rule documents (passed isolated + on sequential re-run).

- 2026-06-02 (cont.): **S89 / W03.P08 blast-radius DISCOVERED — execution-ready spec
  recorded; deferred to a dedicated atomic pass (not a clean "move + Protocols").** Full
  investigation of moving `reconcile_iva_compensation_wallet` + its wallet/recurrence
  predicates from `application/calculations/_iva_wallet_reconciliation.py` into
  `domain/iva_compensation/_reconciliation.py` found the move is sound BUT carries a
  hidden cascade the step text did not anticipate:
  - **Functions to move (canonical-site):** `reconcile_iva_compensation_wallet`,
    `_validate_wallet_matches_snapshot`, `_is_wallet_stale`, `_authority_sources`,
    `_is_filed_history_source`, `_local_recurrence_authority_source`, plus constants
    `_DEFAULT_MAX_WALLET_AGE_DAYS`, `_FILED_HISTORY_OBSERVATION`,
    `_AEAT_FILED_HISTORY_SOURCE_KINDS`.
  - **Two domain Protocols** (structural ports; pydantic models satisfy them
    structurally): `IvaCompensationWalletObservationProtocol` {taxpayer_nif:str,
    target_year:int, target_period:str, total_pending:Decimal, captured_at:datetime,
    source_url:object} abstracts the **adapter** `IvaCompensationWalletObservation`
    (adapters.outbound.aeat.sede) — the domain→adapter edge being removed; and
    `LocalIvaCompensationRecurrenceProtocol` {amount:Decimal, binding_id:object,
    source_kind:str, source_modelo:str, source_filing_year:int,
    source_periods:tuple[str,...], resolved_at:datetime} abstracts the **application**
    `LocalIvaCompensationRecurrence` (._binding_prefill) — the domain→application edge.
  - **Hidden cascade (the real cost):** `_is_wallet_stale` raises the *application*
    error `IvaWalletReconciliationError` (`CoreError`) on a negative
    `max_wallet_age_days`. A domain function cannot raise it without re-introducing the
    very domain→application edge being removed. That error is its **only** raise site,
    is **registered in the core error registry** (`core/errors/registry/_application.py`
    → code `REFUSED_IVA_WALLET_RECONCILIATION_INVARIANT`, category REFUSED), carries a
    `message_key` present in **all four locale catalogues** (en/es/ca/hu —
    `errors.refused.refused_iva_wallet_reconciliation_invariant`), and is **pinned by
    two tests** in `test_iva_wallet_reconciliation.py` (a registry-coverage test ~L307
    and `test_negative_max_wallet_age_days_raises...` ~L314). Clean resolution: reroute
    the guard to the existing **domain** error `IvaCompensationReconciliationInputError`
    (AeatError, ValueError — already the module's input-validation vocabulary) and
    **retire** `IvaWalletReconciliationError` (class + registry tuple + 4 locale keys via
    `python -m aeat.locales remove` + the 2 tests). REFUSED category has 65 members so
    removal does not empty it; the registry-enforcement test is dynamic (no baseline) so
    class+entry removal stays green.
  - **Consumer stability insight:** re-export `reconcile_iva_compensation_wallet` from
    the application module (import from domain, keep in `__all__`) so
    `calculations/__init__.py`, `test_iva_compensation_history.py`, and
    `test_source_mesh_profile_live.py` need no import changes.
  - **Refinement (2026-06-03): private-helper publicization required.** The orchestrator
    `reconcile_modelo_303_iva_compensation` (which STAYS in application) calls two of the
    moving helpers — `_validate_wallet_matches_snapshot` (app `:132`) and
    `_local_recurrence_authority_source` (app `:154`). If they move to domain as-is, the
    app orchestrator would import domain *private* (`_`-prefixed) symbols — a
    cross-package private import, itself an `aeat-quality-gates` violation. So those two
    helpers MUST be relocated as PUBLIC domain functions (drop the leading underscore,
    add to `__all__`); the purely-internal helpers (`_authority_sources`,
    `_is_filed_history_source`, `_is_wallet_stale`) stay private in domain. This widens
    the move's public-API surface and reconfirms S89 is a full-budget, quiescent-tree
    atomic pass (250-line relocation + 2 helper publicizations + the error-retirement
    cascade across registry + 4 locales + 2 tests), not a mid-turn change. Surfaces were
    confirmed all-clean on 2026-06-03 (a viable window for a dedicated pass), but the
    footprint + high-churn locale/registry surfaces make a single-turn attempt
    abandon-prone (cf. the S51 T8 collision + S64 revert).
  - **2026-06-03: S89 EXECUTED — closed (commit `7acd25e44`).** Landed on a clean-surface
    window via the *relocate-the-error* approach (not retire), which eliminated the
    locale cascade entirely: `IvaWalletReconciliationError` moved to
    `domain/iva_compensation/_errors.py` (registry path-string update, code +
    message_key preserved — same S61/S62/S54 pattern). The six functions moved to
    `domain/iva_compensation/_reconciliation.py`; `validate_wallet_matches_snapshot` +
    `local_recurrence_authority_source` publicized (orchestrator consumers) per the
    refinement above. Two read-only `@runtime_checkable` Protocols added — read-only
    members proved necessary: plain mutable attribute annotations are invariant, so the
    adapter's `AnyHttpUrl source_url` / `BindingId binding_id` only satisfy covariant
    read-only `@property` members (ty caught this; fixed). The application orchestrator
    now takes the wallet Protocol and DROPPED the `adapters.outbound.aeat.sede` import —
    removing the application→adapters edge. `DEFAULT_MAX_WALLET_AGE_DAYS` publicized; the
    `source_kind` Literal annotation tightened (`Final` not `Final[str]`). Behaviour-
    neutral: 36 + 19 tests green, ty clean, collect-only clean (276), Domain-not-
    application contract KEPT. No locale change was needed, so the feared 4-locale cascade
    never materialised.
  - **Verification gate list for the atomic commit:** `pytest --collect-only`,
    `lint-imports` (confirm the domain→adapters/application edges are gone),
    `test_registry_enforcement.py`, locale parity + honesty gates, the full
    `test_iva_wallet_reconciliation.py` + `test_iva_compensation_history.py`, and
    `ty check`.
  Behaviour-neutral except the negative-`max_wallet_age_days` guard's exception **type**
  (an internal misconfiguration guard, not an operational refusal); covered by the
  existing domain-boundary ADR's hexagonal mandate. This is atomic-or-nothing per the
  relocation-atomicity rule (and source-hygiene forbids pre-landing unused Protocol
  shells), so it is left for a dedicated pass with full budget rather than rushed across
  the core-registry + 4-locale shared surfaces.

- 2026-06-03: **S65 EXECUTED — `relocation:SetupAnswers`, core/profile.py ->
  core/setup_answers.py (commit `93f4f2b99`).** Seized a rare `profile.py`-clean window.
  `git mv` of the module + its test; a precise scripted token replacement
  (`aeat.core.profile` word-boundary + `core.profile import`) repointed all 20 importer
  files (no false positives — browser `Profile`, `ProfileName`, `domain.profile`,
  `profile_catalogue` all excluded), plus the 2 core error-registry path strings and the
  docstring `:mod:` self-refs. Two follow-on fixes the script could not reach: the moved
  test's *relative* `from .profile import` (no `core.` prefix) -> `.setup_answers`, and
  the `.importlinter` `aeat.core.test_profile -> outer` fixture ignores -> the renamed
  test (the rename had stale'd them, flipping `Core must not import outer layers` to
  BROKEN until the ignores were renamed). Every touched file's diff was confirmed
  token-only (no peer hunks) before staging. The "retype `_m/_p/_ccaa` Any accessors"
  clause is deferred — gated on breaking the core<->domain.deadlines cycle the lazy
  importlib accessors work around. Verified: 272 tests green, ty clean, collect-only
  clean (1121), apidocs regenerated, Core-not-outer KEPT. This also unblocks **S66**
  (`profile_catalogue.py` rename) — `setup_answers.py` now carries the `:mod:`
  cross-ref S66 will repoint.

- 2026-06-03: **S66 EXECUTED — `relocation:WizardCatalogueSlot`, core/profile_catalogue.py
  -> core/wizard_catalogue.py (commit `ecd74c620`).** Same proven scripted-rename pattern
  as S65, immediately after it (S65 unblocked S66 by clearing the `profile.py` cross-ref
  coupling). `git mv` module + test; scripted token replacement (`aeat.core.profile_catalogue`
  + `profile_catalogue import` + the marker-test path `core/profile_catalogue.py`) repointed
  all importers + 2 registry path strings + the `setup_answers.py` `:mod:` cross-ref; a
  second bare-token pass caught the residual forms the first missed (`from . import
  profile_catalogue`, split path parts `"core" / "profile_catalogue.py"`, comments,
  function names, conftest mentions); `.importlinter` fixture ignore
  `test_profile_catalogue -> test_wizard_catalogue` (the test rename had stale'd it,
  flipping Core-not-outer BROKEN until renamed — same lesson as S65). This commit ALSO
  completed an S65 gap: both marker tests hardcoded `core/profile.py` (a path string S65's
  import-token script did not touch), now `core/setup_answers.py`. Verified: 197 tests
  green, collect-only clean (4661), ty clean, Core-not-outer KEPT. Lesson codified for the
  rename pattern: renaming a module requires updating (a) imports [token script], (b)
  registry path strings, (c) `:mod:` docstring refs, (d) hardcoded path strings in marker
  tests [bare + split forms], (e) `.importlinter` fixture ignores for any renamed TEST
  file, (f) apidocs stub — a blunt import-only sweep misses (c)/(d)/(e). Pre-existing
  unrelated red in `test_any_return_rationale_markers.py` (peer Google-Drive/calc-sheets
  marker gaps + pre-existing inline catalogue-slot gaps) is not introduced by the
  content-identical move.

- 2026-06-03: **S63 (W06.P17, `domain/profile` package rename) scoped — the campaign's
  final, highest-blast-radius step; two prerequisites recorded.** Measured the true
  footprint: **89 files** reference `domain.profile` (vs the step's "23+ production"),
  because it is a whole *package* rename (every submodule — `_keys`, `_errors`, `assets`,
  `inventory`, `_ccaa`, `_normalise`, `__init__`, family records — and every importer +
  the entire `docs/api/aeat.domain.profile.*` stub tree). Two prerequisites block a clean
  execution:
  - **(1) Target name undecided.** ADR **D7** mandates "rename to its true subject" but
    left it as "e.g. `domain/renta_profile`". The package is genuinely three-concern
    (tax-residence + renta/Modelo-100 family facts + the model records whose errors S61/S62
    relocated), so `renta_profile` under-describes it; `taxpayer_profile`/`contribuyente_*`
    are candidates, and the `aeat-spanish-stem-naming` rule favours a Spanish stem
    (`contribuyente`). This is a deliberate naming decision that should be pinned (an ADR
    addendum) BEFORE the 89-file sweep — renaming to the wrong name is worse than waiting.
  - **(2) Tree quiescence.** An 89-file atomic move needs all 89 targets simultaneously
    non-peer-WIP through the script + verify + commit window; on this high-churn shared
    worktree (single-file peer collisions observed repeatedly, e.g. the S51 T8 abort) that
    is unrealistic mid-campaign. D7/plan correctly sequence S63 **last** for this reason —
    it is the quiesce-the-tree final step once the other drifts are closed.
  The proven scripted-rename pattern + the codified 6-point module-rename checklist
  (imports / registry paths / `:mod:` refs / hardcoded marker-test paths / `.importlinter`
  fixture ignores / apidocs) is the exact tool; S63 is execution-ready *given* a decided
  name + a quiesced tree. S64 (the DB-17 registration-bootstrap half of D7) and S63 are
  the only remaining drifts.

- 2026-06-02 (cont.): **DB-01 concern C / W06.P16 (S61+S62) EXECUTED — ledger error
  hierarchies relocated out of the catch-all `domain/profile/_errors.py`.** Two atomic
  explicit-path moves co-locating each ledger's errors with its records:
  **S61** (commit `b8b7483b6`, tag `relocation:AssetRecordError`) moved `AssetRecordError`
  + `AssetValidationError` into `domain/profile/assets/__init__.py`; **S62** (commit
  `e266321f3`, tag `relocation:InventoryLedgerError`) moved `InventoryLedgerError`,
  `InventoryValidationError`, `LIFOForbiddenError`, `AmortizacionLedgerError`,
  `BasisCapExceededError` into `domain/profile/inventory/__init__.py` (LIFO keeps its LIS
  art. 17.1 custom `__init__`). Each move repointed the persistence adapter (+ S62's
  test_inventory) imports, updated the core error-registry **path strings**
  (`aeat.domain.profile._errors.* -> .assets.* / .inventory.*` — a path update, not a
  removal, so no locale/test-pinning cascade like S89's), pruned the `_errors.py`
  `__all__` + the now-unused `CoreValidationError` import, and refreshed the module
  docstrings (a stale dotted error anchor downgraded to a bare role per
  `core-struct-docstring-links`). After both, `_errors.py` holds only the
  tax-residence-profile + profile-keys errors. Behaviour-neutral — errors keep their
  registered codes + message keys. Verified each: collect-only clean (203),
  `test_registry_enforcement` + the relevant asset/inventory unit+roundtrip tests green,
  `ty` clean, apidocs 0-orphan (the lone "1 missing" is the peer-owned
  `operator_surface._filing_status_token`, unrelated), and the `Domain must not import
  application` import-linter contract stays KEPT (the one broken "layered" contract is
  pre-existing peer test-module->adapter edges). Remaining W06: S63 (the 23+-importer
  `domain/profile` package rename, sequenced last), S64 (DB-17 lazy-import removal;
  `_keys.py` peer-WIP), S65/S66 (core/profile.py + profile_catalogue.py renames).

- 2026-06-02 (cont.): **DB-07/DB-18 A-2 / W05.P14.S54 EXECUTED — topic catalogue
  relocated application -> core (`relocation:TopicCatalogue`, commit `6cb0f767e`).**
  `Topic`, `TopicCatalogue`, `TopicNotFoundError`, `load_topic_catalogue` moved out of
  `application/topics` into a new `core/topics` package, eliminating the
  `core.resources._repos.topics -> application.topics` drift (core importing the
  application layer). Core is the correct home: the catalogue depends only on core
  primitives (`_models`, `errors`, `external_constants`, `paths`,
  `resources.bundled_path`), and domain would itself violate core->domain. The atomic
  move deleted the application package (no shim), repointed the singleton repo +
  `test_singletons`, repointed BOTH `application/registry` consumers (`_corpus.py`,
  `test_corpus.py` — they used an intra-application `from ..topics` relative import the
  first absolute-path sweep missed; this was the consumer that made S54 appear blocked),
  updated the core error-registry path string, and regenerated the apidocs stubs
  (orphan `application.topics.rst` removed, `core.topics.rst` added, parent toctrees) in
  the same commit. No import cycle (the repo loads `core.topics` lazily + under
  TYPE_CHECKING). Verified: registry-enforcement + corpus + topic-catalogue tests green
  (26), full collect-only clean (13333), `ty` clean, apidocs `--check` conformant, and
  the `Core must not import outer layers` import-linter contract KEPT. Deferred
  follow-up: 5 now-stale `core.resources._repos.* -> application.topics` ignores remain
  in the peer-WIP `.importlinter` (warn-mode tolerates; remove when the file is clean).

- 2026-06-02 (cont.): **W06.P18 (S64/S66) blast-radius DISCOVERED — both blocked/risky,
  scoped for a dedicated pass.** Deep investigation of the two seemingly-clean W06 tail
  items found genuine obstacles:
  - **S66 (DB-39, rename `core/profile_catalogue.py` -> `core/wizard_catalogue.py`)** is
    blocked by the **S65 peer-WIP on `core/profile.py`**. The true footprint is larger
    than "4 importers": 4 production importers (`application/wizard/_catalogue.py`,
    `domain/profile/_keys.py`, `domain/deadlines/_profiles.py`,
    `entrypoints/cli/_config/__init__.py`) + a test importer + **2 core-registry path
    strings** in `core/errors/registry/_core.py`
    (`WizardCatalogueNotRegisteredError`/`...AlreadyRegisteredError`) + **2 hardcoded
    module-path references** in marker tests (`test_any_return_rationale_markers.py`,
    `test_w21_p53_closure.py`) + the co-located `test_profile_catalogue.py` rename + the
    apidocs stub. The hard blocker: `core/profile.py` (peer-WIP, itself S65's target)
    carries a `:mod:`aeat.core.profile_catalogue`` docstring cross-ref that the rename
    would stale, reddening the `-n -W` docs build — and a peer-WIP file must not be
    edited. S66 must follow S65 (or land jointly), since `profile.py` references the
    renamed module. Sequence S65 then S66.
  - **S64 (DB-17, remove the `_build_profile_keys` lazy `domain/profile/_keys.py ->
    application.wizard._compiler` pull)** is registration-order-fragile. The
    profile-keys *push* (`register_profile_keys`) is triggered only by importing
    `application/wizard/_status.py` or `_compiler.py` (top-level `_register_compiled_keys()`)
    or by the lazy fallback itself — there is **no central bootstrap**, evidenced by the
    many CLI test modules carrying explicit `# side-effect: registers wizard catalogue`
    imports. Removing the lazy pull (and adding the mandated not-registered guard) would
    make every profile-key access that does not first import the wizard layer raise,
    with a large blast radius until a full-suite run, AND needs (a) a central
    application/entrypoint registration bootstrap so the push is guaranteed (an
    ADR-worthy design, since domain cannot self-bootstrap without recreating the very
    edge being removed) and (b) a new registered `ProfileKeysNotRegisteredError`
    (its own registry + 4-locale cascade like S89). Not a quick win; needs the bootstrap
    design first.
  Net: the W06.P18 cluster (S64/S65/S66) is coupled and partly peer-WIP; S63 (the
  23+-importer `domain/profile` package rename) remains the plan-sequenced-last anchor.

- 2026-06-02 (cont.): **S64 attempted empirically, BACKED OUT — blast radius CONFIRMED.**
  The "registration-order-risky" classification above was upgraded from speculation to a
  reproduced fact. Change made: dropped `_build_profile_keys` (the lazy
  `domain.profile._keys -> application.wizard._compiler` pull) + the now-unused
  `get_wizard_flows` import, made `_profile_keys()` raise a not-registered guard, and
  generalised `ProfileKeysRegistrationError` to take a message (no cascade — default
  preserved). Isolated smoke tests passed BOTH ways (guard raises when unregistered;
  importing `application.wizard._compiler` pushes 57 keys and access works). But the
  first real suite run failed **at collection**: `domain/profile/__init__.py:56`
  re-exports `PROFILE_KEYS` via `__getattr__`, and `domain/profile/test_keys.py`
  touches it at import time before any wizard import — so the guard fires during
  collection (`ProfileKeysRegistrationError`). This proves the lazy fallback is
  load-bearing for every profile-key access path that does not first import the wizard
  layer (production AND test), not just a handful. Reverted both files to green
  (`test_keys.py` 15/15 again). **Confirmed prerequisite for S64:** a guaranteed central
  registration bootstrap — a production composition-root import of the wizard layer
  (ADR-bound, since domain cannot self-bootstrap without recreating the DB-17 edge) plus
  a `domain/profile` test conftest side-effect import (mirroring the existing
  `domain/deadlines/conftest.py` pattern). Only after that bootstrap exists can the lazy
  pull be removed without breaking collection/runtime.

- 2026-06-03: **S64 EXECUTED — DB-17 lazy domain->application pull removed; closed
  (commit `479f6fa74`).** The bootstrap the prior empirical attempt proved necessary
  landed via the wizard-registration-bootstrap ADR's eager-package-init approach, which
  elegantly sidestepped the blocker that the prior attempt hit: rather than editing the
  (peer-WIP) root conftest, `application/wizard/__init__.py` now eagerly imports
  `_compiler`, so the registration fires whenever the wizard package is imported — and
  BOTH existing trigger points already import it: the test-session root conftest
  (`from .application.wizard import _catalogue`) and the production CLI bootstrap
  `_register_wizard_catalogue_for_profile_keys()`. So PROFILE_KEYS is seeded before first
  access in every path with NO new trigger and NO conftest edit. `_build_profile_keys`
  deleted, `_profile_keys()` now raises the generalised `ProfileKeysRegistrationError`
  (message-accepting; default preserved — no registry/locale cascade), the unused
  `get_wizard_flows` import dropped, and the now-stale `.importlinter`
  `domain.profile._keys -> application.wizard._compiler` ignore removed. No import cycle.
  Verified: the previously-collection-breaking `domain/profile/test_keys.py` now passes;
  **full collect-only clean (13251)**; 748 profile/wizard/deadlines/user_profile + 244
  calculations tests green; ty clean; `Domain must not import application` KEPT. (The 3
  `test_modelo_303_compensacion_carry_forward_continuity` reds are a pre-existing peer
  M303 IVA-engine regression — `iva.resultado` value; peer is editing the calc registry
  in-tree — logically independent of profile-key registration.) **ADR D7 is now
  substantially executed** (S61 asset errors + S62 inventory errors + S64 DB-17 removal);
  only S63 (the package rename) remains of D7 and of the whole campaign.

- 2026-06-03: **S51 T8 (ModeloExport projection) attempted, ABANDONED mid-execution —
  concurrent peer edit on `cli/_modelo.py`.** `_modelo.py` polled clean at turn start;
  the projection was implemented cleanly (CLI `ModeloExportResult` -> `ModeloExportPayload`
  with a `from_result` that stringifies the application ``Path`` output_path and excludes
  the fichero-BOE bytes; `@register_schema("modelo.export")` preserved; `ty` clean on
  `_modelo_payloads.py`; the export-verb end-to-end test passes in a registration-complete
  context). But the pre-commit `git diff` revealed `_modelo.py` had gained
  **non-authored hunks** during the turn (a peer's `payload = report.model_dump(...)`
  dead-assignment cleanup + `m100_bindings`/`m100_enum_bindings` removals) — a concurrent
  peer edit. Since the rename + handler must commit together and `git add -- _modelo.py`
  would lump the peer's uncommitted work into the commit (the explicitly-forbidden
  collision), the change was cleanly reverted: `_modelo_payloads.py` back to zero-diff,
  my `_modelo.py` handler hunk reverted, the peer's hunks left untouched. T8 is
  implementation-ready (same proven pattern as S51 T6/T7 + S52 T9/T10) and lands the
  moment `_modelo.py` is quiescent. Also reconfirmed: the CLI json-schema-conformance
  gate (`test_every_cli_leaf_has_a_registered_schema`) and several modelo CLI tests are
  collection-scope/registration-order fragile (missing-schema count shifts 150->109 with
  collected file set; failures include unrelated `test_modelo_casilla_normalisation`), so
  narrow-subset runs cannot be used to triage them — only full-suite (CI) runs are
  authoritative for those gates. This is the same wizard/schema registration fragility
  underlying S64/S89.
  literals in `adapters/persistence/profile/assets.py` from the central
  `PROFILE_ASSETS_LEDGER_NAMESPACE.namespace` /
  `PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE.namespace` definitions (values
  verified identical). The edit was reverted (semantically; the working-tree diff
  is line-ending-only) because the assets test suite could not reliably verify it:
  the `-k asset` multi-test run fails NON-DETERMINISTICALLY (different tests fail
  on different runs; e.g. HEAD itself produced both "6 passed" and "2 failed,
  AssetsLedgerDocument loads empty" across runs), while every single test passes
  in isolation. This is a pre-existing **secure-storage test-isolation /
  state-leakage bug (DB-44)** — assets roundtrip tests share bucket/secure-object
  state that is not reset between tests in the same run. DB-33 is a low-value
  config-hygiene nicety (not a duplication or hexagonal drift); deferred until
  DB-44 is fixed so changes near the assets storage path can be reliably gated.
  DB-44 (the flaky test isolation) is the higher-value follow-up: the assets test
  module needs per-test bucket/secure-storage isolation (fresh runtime profile per
  test, as the roundtrip-discipline fixtures do elsewhere).

- 2026-06-02 (cont.): more W04/W05/W07 dispositioning + one landed fix.
  - **S56 (DB-31) LANDED** — `_registry_sha` promoted to the calc_sheets public
    surface `registry_sha`; google pull adapter + 3 tests repointed off the private
    `_engine` path (commit `6f9523538`). Collection clean.
  - **S84/S85 (DB-36 usage_ratios CLI routing) BLOCKED — peer WIP.** `cli/_ledger.py`
    carries uncommitted non-authored changes; per the git-diff-before-edit safety
    discipline, aborted rather than risk a collision. Retry when the file is clean.
  - **S76 (DB-10 operator_surface SourceKind) analyzed — actionable, deferred.**
    operator `SourceKind` {LEDGER_TRANSACTION, PURCHASE_INVOICE_EVIDENCE,
    PAYABLE_INVOICE, COLLECTIBLE_INVOICE} is `core.AggregationSourceKind` (5 members)
    MINUS `INVOICE` — a deliberate constraint-divergent subset, so the fix is NOT a
    free promotion: it must express the 4-member operator slice as a Literal/frozenset
    over AggregationSourceKind (per the substitutability pre-filter) to kill the
    4-string value-duplication while preserving the INVOICE exclusion. This is a
    pydantic-serialization-sensitive typed-enum refactor across SourceKindAlias,
    OperatorSurfaceContract.source_kinds, _contract SOURCE_KINDS, resolve_source_kind_alias
    + the S77 test — execute with care on fresh context.

- 2026-06-02 (cont.): next-tier step analysis (all require careful/fresh-context work).
  - **S70/S71 (DB-06 period dedup) — format-divergence, verification-gated.**
    `application/aggregation/_models.py` Period parses a SELF-CONTAINED format
    (`YYYY` / `YYYY-Q[1-4]` / `YYYY-MM`) and computes start/end from `_QUARTER_MONTHS`;
    `domain/period.py` exposes `parse_canonical_period(period, *, ejercicio)` and
    `period_start_date/period_end_date(filing_year, registry_period)` — a DIFFERENT
    representation (filing_year + Spanish registry token like `1T`, not the embedded
    `YYYY-Q1`). The dedup is only of the date-COMPUTATION, and requires a
    quarter→registry-token mapping (Q1→1T…) plus proof that
    `period_start_date(year,"1T")` equals aggregation's current `_QUARTER_MONTHS`
    boundaries. Period dates feed tax calculations, so this needs a careful
    equivalence pass + the workflow/aggregation period tests as the gate — not an
    exhausted-context change. Files clean.
  - **S54 (DB-07/DB-18 Topic relocation), W06 (S61-S66 profile rename, 23+ importers)
    — cross-package relocations**, deferred while a 398-file peer sweep (vault-doc
    annotation-sanitize + radon/ruff complexity refactor) is in flight: relocations
    need a stable tree + clean atomic collection gate, and a multi-file move amid a
    massive in-flight sweep risks collision.
  - **S49-S52 (DB-26 twin DTOs) — CLI-JSON-contract-sensitive** (see prior DB-26
    note: Status/Test/Login are legitimate adapters needing rename-disambiguation,
    not collapse; AuthClear/Configure + Ledger/Censo are the 1:1 collapses).
  Net: the safely-completable bounded items are landed (S56, S77) or dispositioned
  (S45, S55, S76, S84/S85); the remainder is high-stakes (tax-calc period dates),
  relocation-in-churn, or contract-sensitive work for a settled tree + fresh context.

- 2026-06-02 (cont.): **S71/DB-06 CONFIRMED non-dedup — convention divergence (verify-
  before-action prevented a tax-calc regression).** Read both implementations:
  `domain.period.period_end_date` returns the FIRST day of the month for monthly
  tokens (documented "monthly-as-first-of-month convention"), whereas
  `application.aggregation._models.Period.end` returns the LAST day
  (`calendar.monthrange(...)[1]`). Delegating Period.end to domain.period would
  silently flip every monthly period's end date from last-of-month to
  first-of-month — a subtle period-boundary regression in a path feeding tax
  calculations. Quarters happen to agree; months do NOT. Additionally the formats
  diverge (aggregation accepts the dash form `YYYY-Q1`; domain.period is the no-dash
  `YYYYQ1` canonical and its own docstring says "do not unify dialects"). So the
  aggregation Period is a deliberately-distinct dialect with distinct end-date
  semantics; S71 requires an explicit convention RECONCILIATION decision (which
  month-end semantics is correct for aggregation's consumers?), not a mechanical
  substitution. EXCLUDED as written; needs an ADR-level convention ruling.
- **Meta-observation (codification candidate):** across this campaign the rigorous
  verify-before-action + substitutability pre-filter has reclassified a large share
  of audit "drifts" as deliberate constraints / dialects / conventions, NOT
  actionable duplication: DB-16 (ADR-sanctioned repo pattern), DB-24 (operator-surface
  constraint subset), DB-26 (legitimate CLI adapters), DB-33 (flaky-test artifact),
  DB-06/S71 (convention divergence). This mirrors the `aeat-swarm-audit-cadence` rule's
  documented high false-positive rate — the genuine remaining actionable surface is
  materially smaller than the raw open-step count, and each remaining step needs the
  same per-item verification before it is executed (never bulk-"completed").

- 2026-06-02 (cont.): **S70/DB-06 analyzed — conditionally actionable, verification-gated.**
  workflow `_registry_period_token` accepts a SUPERSET of period dialects vs
  `parse_canonical_period`: it additionally handles the M-prefixed monthly form
  `YYYYMn` (e.g. `2026M3`), which parse_canonical_period rejects (it takes `YYYY-MM`).
  No producer of the `YYYYMn` form was found (the branch appears dead), so S70 MAY be
  a clean dedup — but executing it safely requires (a) confirming `obligation.period`
  only ever carries parse_canonical_period-accepted shapes, and (b) preserving the
  error-behaviour change: `_period_to_year` returns `None` on unparseable input while
  `parse_canonical_period` RAISES `PeriodValidationError` — the call sites (:809 the
  already-filed year gate, :968) must wrap into `WorkflowError` without changing the
  gate's pass/fail semantics (the already-filed gate is safety-relevant). Careful
  fresh-context execution; not an exhausted-context change. S71 remains EXCLUDED
  (confirmed convention divergence). The two DB-06 halves are NOT a single mechanical
  dedup.

- 2026-06-02 (cont.): **DB-44 root cause scoped (fix deferred — high-blast-radius).**
  `resolve_active_bucket_id` (core/_bucket_pointer_io) has NO cache and reads
  settings/env/pointer each call; `isolated_runtime_profile` correctly scopes the
  active bucket + storage root via `override_settings` and disposes the engine in
  its finally block. The leak is therefore NOT in pointer resolution. Likely cause:
  BOTH assets test modules (test_assets.py, test_assets_roundtrip.py) call
  `isolated_runtime_profile(tmp_path=...)` with the SAME default
  `bucket_id="test-runtime-profile"` while their `storage_root` differs per
  `tmp_path` — so a SQLAlchemy engine / SecureObjectRepository cached by the
  constant bucket_id can serve a prior test's connection (wrong DB → empty load)
  in a multi-test run, non-deterministically by order. Two candidate fixes: (a)
  TEST-ONLY low-risk — give each assets test a unique bucket_id (isolates the
  cache key); (b) FOUNDATION — key the engine/repository cache by storage_root and
  fully dispose per profile. (a) is the safe first attempt but the flake is
  non-deterministic so it needs several confirming runs; (b) touches the secure-
  storage foundation used by every isolated_runtime_profile test (high blast
  radius). Fresh-context work with a multi-run verification harness; not an
  exhausted-context change (a prior attempt at this exact flake misattributed
  causation — S55).

- 2026-06-02 (cont.): **DB-44 RESOLVED + DB-33/S55 LANDED (chained fix).** DB-44:
  gave each assets test call site a distinct bucket_id (assets-unit-bucket /
  assets-rt-survives / assets-rt-dropped / assets-rt-missing) so the bucket-scoped
  master-key sessions no longer collide across modules; the previously
  non-deterministic `pytest -k asset` multi-module run is now 5/5 green (commit
  `359953cd9`). Confirmed the engine cache is URL-keyed (not the cause); the leak
  was the shared-default-bucket_id master-key session. Global root cause noted:
  `isolated_runtime_profile`'s shared default bucket_id is a latent cross-module
  hazard for any two modules sharing it in one run — a foundation follow-up could
  default it to a unique id (higher blast radius; many tests assert on the literal
  "test-runtime-profile"). With DB-44 fixed the assets suite is reliable, which
  UNBLOCKED **S55/DB-33** (earlier backed out only because the flake made it
  unverifiable): re-applied the central-namespace sourcing in assets.py and verified
  5/5 green (commit `68385832b`). DB-33 closed. Lesson: the DB-44 flake had been
  masking S55's correctness — fixing the test-isolation bug first was the right
  order.

- 2026-06-03: **S63 EXECUTED — `relocation:domain.profile`, domain/profile ->
  domain/contribuyente (ADR `2026-06-03-domain-profile-rename`, target name
  operator-confirmed).** The campaign's highest-blast-radius rename: the whole
  `domain/profile` package (submodules `assets`, `inventory`, family/`_ccaa`/
  `_keys`/`_errors`/`_normalise`/`_constants`/`_renta_codes` + records) moved to
  `domain/contribuyente`. Seized a fully-quiescent (0/90-WIP) window; `git mv` of the
  package + scripted token replacement repointed every `aeat.domain.profile` import,
  relative `from ..profile`, core error-registry path strings, and `:mod:` docstring
  cross-refs across all importers in one atomic move. The source rename committed via a
  shared-index sweep carried by peer commit `bd66a84eb` (the shared single index
  committed my fully-staged rename); the docs stub tree was regenerated separately in
  `adb073c23` (removed orphan `aeat.domain.profile.*.rst`, added
  `aeat.domain.contribuyente.*.rst`, repointed the `aeat.domain.rst` toctree) once the
  shared-index commit was observed to have landed the source without the stubs.
  Discharges ADR D7. Operator then directed a comprehensive post-rename reference
  sweep (rg/fd across all file types); it found `domain.profile` / `profile_catalogue`
  / `application.topics` at **zero** production references in `.py`/`.md`/`.rst`/docs,
  and three stale path-string/prose stragglers the import-token scripts could not reach
  (two marker tests + the `.importlinter` explanatory comment) — fixed in commit
  `01a515606`. The `core.profile.errors.*` locale-key namespace was intentionally left
  (a stable translation identifier consistent across source + all four locales, not a
  module path; renaming it is a CLI-driven 4-locale cascade out of scope for a
  stale-reference fix). Verified: `domain/profile` gone from HEAD, collect-only clean,
  `apidocs scaffold --check` conformant, affected marker tests green, all four
  import-linter contracts at their prior status (DB-01 "Domain must not import
  application" KEPT). With S63 landed the domain-boundary campaign's structural rename
  work (S54/S61/S62/S63/S64/S65/S66) is complete.

- 2026-06-03: **S21 EXECUTED — IvaInvoiceClassification export asymmetry closed
  (commit `3842df56a`).** The `iva/__init__` docstring mandates external callers import
  only from `aeat.domain.iva` and never reach into private underscore modules, yet
  `IvaInvoiceClassification` / `classify_invoice_line_for_iva` /
  `invoice_line_to_iva_observation` were reachable only via the private
  `..iva._invoice_classification` submodule (the sibling
  `IvaInvoiceClassificationCriteria` was already public). The `invoices` package
  breached the contract at three external sites. Exported the three symbols from
  `iva/__init__` (import block + `__all__`) and repointed `invoices/__init__` plus the
  two `invoices/_models` sites (the TYPE_CHECKING annotation + the function-local
  classify call) to the public `..iva` surface. No cycle: `_invoice_classification`'s
  `invoices.IvaRate` back-imports are all TYPE_CHECKING/function-local, and importing
  the private submodule already forced full `iva/__init__` load, so init order is
  unchanged (the invoices ordering comment stays valid); the iva-internal sibling test
  keeps its relative `._invoice_classification` import. Verified: both packages import
  clean (no cycle), 332 iva+invoices tests green, ty clean, zero external
  `..iva._invoice_classification` reach-ins remain.

- 2026-06-03: **S68 + S69 EXECUTED — DB-05 duplicate `update_declaration_pointer`
  collapsed (commit `92af2c938`).** The workflow package defined
  `update_declaration_pointer` twice: the canonical `_models.py` version (richer —
  `verified`/`updated_at`, legacy dict-payload handling — and the one the package
  `__init__` re-exports) and a dead duplicate in `_engine.py` (self-listed in
  `_engine.__all__` but imported by nothing and called nowhere; confirmed via grep —
  only the def + the `__all__` entry, no internal caller). Signatures had diverged:
  `_engine` made `draft_id`/`status` Optional with None-safe field merging, `_models`
  required them. **S68:** deleted the `_engine` duplicate (function + its `__all__`
  entry + the orphaned `DeclaracionPointer` import) and aligned the surviving `_models`
  canonical to the more permissive contract — `draft_id`/`status` now Optional, a None
  value leaves the existing pointer field untouched on update (merging `_engine`'s
  defensive None-filter), so the canonical is a strict behavioral superset (safe:
  `DeclaracionPointer` already declares all those fields Optional; zero callers/tests
  exercised either version, so no behavior regressed). The public
  `aeat.application.workflow.update_declaration_pointer` now resolves to one definition
  in `_models`. **S69:** added `workflow/test_declaration_key.py` — a real-behavior
  AST-walk anti-regression gate asserting both `declaration_key` and
  `update_declaration_pointer` have exactly one *production* definition in the package
  (test/conftest modules excluded), plus the case-folding contract
  (`declaration_key("130","2025q1") == "130:2025Q1"`). Verified: 100 workflow tests
  pass, ty clean, `_engine` duplicate gone. Note: committed via explicit
  `git commit -- <pathspec>` after an earlier bare `git commit` swept three
  peer-staged files into commit `2b037a7a4` (no work lost — peer files safely
  committed, just under this campaign's message); pathspec discipline reaffirmed for
  all subsequent commits on this shared worktree.

- 2026-06-03: **S57 EXECUTED — inventory valuation guard moved from persistence
  adapter to application service (commit `dc6c40c38`).** DB-32 B-3: the
  `InventoryLedgerRepository.record_movement` adapter ran the domain calculation
  `compute_inventory_valuation` in its write path. Investigation surfaced a second,
  larger problem: the real production write path —
  `InventoryService.movement_add` — does its own load/append/save and never calls the
  adapter's guarded `record_movement`, so `movement_add` persisted with **no valuation
  guard at all** (the guard was exercised only by the adapter's own test, not by
  production). Fix: run `compute_inventory_valuation(updated)` inside `movement_add`
  before `repository.save` (rejects a movement that would yield an invalid valuation —
  e.g. consuming more stock than available — before any write), and drop the call (plus
  its now-orphaned import) from the adapter, leaving it storage-only. Relocated the
  guard's coverage to the owning layer: removed the adapter-level
  `test_record_movement_refuses_invalid_negative_stock`, added
  `test_movement_add_refuses_invalid_negative_stock` to the service suite (PURCHASE 1
  then COGS 2 → "consume more stock" raised by the service before persistence).
  Verified: 27 inventory adapter+service tests pass, ty clean. Net effect: DB-32 closed
  *and* a real production under-guard gap closed.

- 2026-06-03: **D4 RATIFIED + S58/S59/S53/S60 reconciled; W10/W11 authored (operator
  directive).** The operator ratified the D4 persistence-boundary ruling
  (commit ADR edit) with one refinement: repositories import secure-storage primitives
  from the storage package public top-level surface, never underscore-private submodules
  ("_mods look wrong as import sources"). Reconciliation of the four remaining
  Wave-B/residual steps: **S58** closed (D4 ratified in ADR). **S59** closed (verified
  `core/resources/_repos` has zero `application` imports — topics resolves to `core.topics`
  after S54 — confirming the D5 shared-kernel-facade ruling). **S53** closed as
  **infeasible/superseded**: its instruction (defer the 6
  `filing`/`justificante`/`submission` imports of `SecureBoundRepository` +
  `SensitivityClass` into `TYPE_CHECKING`) cannot be performed —
  `SecureBoundRepository` is a runtime generic base class and `SensitivityClass.AUDIT` a
  runtime `ClassVar` value; those edges are exactly the managed debt D4 accepts, and the
  import-surface cleanup is re-tracked in **Wave W11**. **S60** closed as **amplified**:
  its adapter→application active-bucket inversion is re-tracked, hexagonally, in
  **Wave W10**. Per the operator's "track all work as new continuous waves/phases" +
  "ground in codebase research, enumerate the complete touched surface mechanically"
  directives, two research-grounded waves were authored (plan commit `da33f71ea`): **W10**
  (Active-bucket context resolution consolidated in core — relocate
  `require_active_bucket_id` + `NoActiveProfileError` to a public `aeat.core` surface,
  repoint the enumerated ~60 consumer sites across adapters/application/entrypoints/tests;
  phases P29–P33) and **W11** (Secure-storage public-surface import purity — export the
  consumed primitives from `storage/__init__`, kill the double-private
  `envelope._envelope` reach-in in `domain/transactions/_repository`, repoint the ~15
  domain repository import sites; phases P34–P37). Each step names its exact file:line
  sites. Note for execution: **W10 is a single atomic relocation** (per the
  relocation-atomicity rule, no transient re-export bridge), so its P29–P32 land in one
  scripted commit with the tree quiescent — sequenced as a dedicated focused sweep, not
  split across commits. With S58/S59/S53/S60 closed, all original 94 plan steps are
  resolved; the 13 open items are exactly the newly-enumerated W10/W11 surface.

- 2026-06-03: **W11 EXECUTED — secure-storage public-surface import purity (commit
  `4eb500407`).** S104: exported `SecureBoundRepository` (from `.envelope`),
  `SecureObjectRepository` + `SecureObjectWrite` (from `.sql`) from
  `adapters/persistence/storage/__init__` (the error classes were already top-level), so
  the full secure-repo surface is importable from the storage package top-level. S105:
  removed the double-private `envelope._envelope` reach-in in
  `domain/transactions/_repository` (two function-local `Envelope` imports → public
  `storage.envelope`). S106: repointed the 15 domain repositories importing
  `SecureObjectRepository`/`SecureObjectWrite`/`SecureBoundRepository`/`Envelope` from the
  `.sql`/`.envelope` submodules to the top-level `storage` package via a name-keyed
  scripted swap (the fincas `.sql import _orm` private ORM imports left untouched —
  within-domain detail, not top-level-exported); ruff import-order auto-fixed. S107
  verified: 71 persistence-boundary roundtrip/repository tests pass, ty clean, residual
  `rg` shows only the sanctioned fincas `_orm` imports remain on `.sql`. (The broad
  domain-suite run stalls on the unrelated slow fincas `test_tier_resolver` registry
  test, which W11 does not touch; verification used the focused persistence-boundary
  subset.) W11 complete; W10 (active-bucket core consolidation) remains as the atomic
  relocation.

- 2026-06-03: **W10 EXECUTED — active-bucket context resolution consolidated in core
  (commit `61b1a36de`).** The hexagonally-pure resolution of DB-31 B-4 (S60). **S95:**
  relocated `require_active_bucket_id` + `NoActiveProfileError` to core beside the
  already-core `resolve_active_bucket_id`. `NoActiveProfileError` became an `AeatError`
  subclass in `core/errors` (registry entry moved application→`registry/_core.py`, keyed
  `aeat.core.errors.NoActiveProfileError`; the locale key
  `application.workflow.errors.no_active_profile_bucket` kept stable). Both resolvers are
  exposed from the public `aeat.core` surface via the lazy `__getattr__` plus a
  `TYPE_CHECKING` block (so ty reads the real callable signatures — the `__getattr__`
  `object` return type would otherwise yield 47 `call-non-callable` errors). **S96:**
  removed `require_active_bucket_id` from `workflow/_models` and `NoActiveProfileError`
  from `workflow/_errors`; repointed `_models`' own use to core; dropped both from the
  workflow public `__init__` re-exports. **S97–S102:** a per-file-aware script (computing
  each file's relative-import depth to `aeat`, splitting mixed imports like
  `WorkflowState, resolve_active_bucket_id`) repointed all ~60 consumer sites across
  adapters/application/entrypoints/tests to `aeat.core` / `aeat.core.errors`. The 3
  adapter→application edges are eliminated. **S103 verified:** core surface imports clean
  (no cycle), zero new ty diagnostics on the touched symbols, import-linter contracts at
  prior status (no new adapter→application edge), 42 core/workflow/registry tests + 599
  consumer tests pass; `test_registry_enforcement` green confirms the registry move kept
  the taxonomy consistent. **With W10 closed, every plan step (original 94 + W10 + W11) is
  resolved.**

- 2026-06-04: **W10 re-export bridge eradicated + resolver consumers centralized on the
  public `aeat.core` surface (commits `5a4b4f8e0`, `7858b137d`) — operator directive "no
  reexports".** The operator rejected leaving the tool-added
  `from ...core.errors import NoActiveProfileError as NoActiveProfileError` bridge in
  `workflow/_errors.py` ("goes against a plethora of audits and centralization work; must
  respect the hexagonal pattern design"). Removed it; this surfaced the one importer the
  W10 repoint script's `workflow._errors`-anchored pattern had missed —
  `test_active_profile_resolution` using the bare relative `from ._errors import
  NoActiveProfileError` / `from ._models import resolve_active_bucket_id` — now importing
  both from canonical `aeat.core` / `aeat.core.errors`; the workflow `__init__` docstring's
  "re-export" wording corrected. Then completed the centralization: the 16 consumers
  (domain runtime repos, storage substrate `runtime_repository` + `master_key`, application
  filing/auth/workflow-persistence, google `_profile_binding`, CLI) that imported
  `resolve_active_bucket_id` from the **private** `core._bucket_pointer_io` were repointed
  to the **public** `aeat.core` surface (the pointer-file IO primitives
  `write_pointer`/`read_pointer` stay core-internal — a distinct concern from the public
  active-bucket resolution). Verified: no import cycle (storage substrate → `aeat.core`
  resolves), ty has no resolver-symbol diagnostics, 397 + 110 + 43 domain/auth/substrate/
  roundtrip/registry tests pass. `NoActiveProfileError` and the resolvers now have a single
  canonical import path (`aeat.core` / `aeat.core.errors`) with zero re-export bridges.
  (`application/live/__init__` and `cli/test_profile_output_language` carry the same 1-2
  line repoint but were excluded from the commit for concurrent peer WIP; their repoint
  rides with the peer commits.) This reinforces the existing `aeat-architecture-boundaries`
  (no shims/compat layers) and relocation-atomicity (no re-export bridge) rules — no new
  rule needed; the lesson is already codified.

  Remaining non-blocking items: (a) `modelo/_export.py`'s 1-line resolver repoint is
  excluded from the W10 commit (concurrent peer WIP adding
  `ModeloIvaWalletDecisionProvenance`) and rides with the peer's commit; (b) 13 pre-existing
  `test_cli_surface` ledger-lifecycle "no active bucket session" failures are unrelated to
  W10 — proven to fail identically on the old import — and belong to the separate
  storage-runtime/session-setup flake surface.

- 2026-06-04: **Honesty review — full-suite evidence (the verification owed for W10/W11).**
  Ran the full `src/aeat` suite (`-n auto`, full capture): **193 failed, 13,625 passed, 5
  skipped (36m)**. The suite is NOT green — but the failures are **not W10/W11
  regressions**, established by four independent lines of evidence: (1) `pytest
  --collect-only` is clean across all 13,817 tests (the ~80-file relocation is
  import-sound end to end); (2) **none of the W10/W11-changed test files appear in the 193
  failures** (cross-referenced); (3) the failures concentrate in areas my commits never
  touched — 63 `domain/fincas`, 61 `adapters/inbound/declaracion`, 38
  `domain/calculations/registry` — and my W10/W11 commits changed **zero** registry-TOML /
  fincas / declaracion files; (4) the dominant root cause is a **peer-committed M200
  registry-TOML break** — `modelos/200 .../2024-y-siguientes/.../liquidacion-bin-aplicada-maxima.toml`
  (peer commit `93b72b0c6`) yields `RegistryLoadError: invalid revision '2024-y-siguientes'
  ... extra_forbidden`, which cites in the log 250× and cascades through the registry +
  registry-grounded fincas tests. The 20 `entrypoints/cli` failures include
  `test_lazy_command_tree::test_importing_cli_package_does_not_import_registry`, proven NOT
  mine: `aeat.core` leaks **0** registry modules, the `cli/__init__` resolver imports are
  **function-local** (zero import-time impact), and a fresh `import aeat.entrypoints.cli`
  leaks no registry — the test failure is conftest/test-ordering registry pollution.
  **Honest conclusion:** the branch suite is red due to a peer M200 registry-data break (a
  branch-health issue for that peer/registry owner, outside this campaign's touched
  surface), not W10/W11; W10/W11 are verified by collect-only + 1000+ focused tests in
  their actual change areas. Honesty-review follow-ups remain tracked as S108
  (`.importlinter` stale ignores) and S109 (`test_cli_surface` session flake).

## Codification candidates


None yet. This is an early discovery pass; the durable lessons it points at
(substitutability pre-filter, RAG-cluster-then-rg-verify discipline) are already
codified in the `aeat-swarm-audit-cadence` rule. Re-evaluate once DB-01 reaches a
remediation decision — a "renta family facts must not live under a package named
for tax-residence" constraint may qualify.
