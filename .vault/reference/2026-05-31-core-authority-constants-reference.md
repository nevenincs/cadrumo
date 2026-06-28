---
tags:
  - '#reference'
  - '#core-authority-constants'
date: '2026-05-31'
modified: '2026-05-31'
related: []
---

# core-authority-constants reference: module-level constant inventory

Audit of every UPPER_SNAKE_CASE module-level constant imported outside its declaring module
across src/aeat/. Grounded in src/aeat/core/external_constants.py,
src/aeat/core/external_constants.toml, .claude/rules/aeat-architecture-boundaries.md,
and .claude/rules/aeat-source-hygiene.md.

## Findings

### 1. Inventory table

| Name | File:line | Layer | Class | Cross-module consumers (production) |
|---|---|---|---|---|
| DEFAULT_CURRENCY | core/external_constants.py:24 | core | string | test only |
| BINARY_MIME_TYPE | core/external_constants.py:27 | core | string | test only |
| JSON_MIME_TYPE | core/external_constants.py:30 | core | string | test only |
| CSV_MIME_TYPE | core/external_constants.py:33 | core | string | test only |
| CLASSIFIED_BY_MANUAL | core/external_constants.py:38 | core | string sentinel | test only |
| CSV_ENCODING_FALLBACK_CHAIN | core/external_constants.py:303 | core | tuple | adapters/inbound/financial (test) |
| PROJECT_ROOT [1] | core/config.py:60 | core | path | application/diagnostics.py, adapters/outbound/llm (DUPLICATE SRC) |
| PROJECT_ROOT [2] | core/paths.py:23 | core | path | adapters/inbound/declaracion/_parser.py (DUPLICATE SRC) |
| M347_THRESHOLD_EUR | domain/modelos/_row_models.py:276 | domain | Decimal threshold | entrypoints/cli/_modelo.py |
| APPROVAL_BASIS_VERSION | domain/filing/_schema.py:25 | domain | string | application/filing/__init__.py |
| TX_BUCKET_NAMESPACE | domain/transactions/_repository.py:28 | domain | string | application/ledger/_actions.py |
| AEAT_GROI_URL | domain/calculations/registry/_groi_oracle.py:64 | domain | URL | adapters/outbound/aeat/sede/_groi_check.py |
| GROI_ORACLE_ID | domain/calculations/registry/_groi_oracle.py:60 | domain | string | adapter test only |
| AEAT_NIF_IVA_VERIFICATION_URL | domain/calculations/registry/_aeat_nif_iva_oracle.py:44 | domain | URL | adapters/outbound/aeat/sede/_nif_iva_check.py |
| AEAT_NIF_IVA_ENTRY_URL | domain/calculations/registry/_aeat_nif_iva_oracle.py:50 | domain | URL | adapters/outbound/aeat/sede/_nif_iva_check.py |
| M210_DEFERRED_TIPO_SENTINEL | domain/calculations/registry/_formula_runtime.py:55 | domain | Decimal sentinel | domain-internal |
| M210_CONVENIO_MISSING_SENTINEL | domain/calculations/registry/_formula_runtime.py:56 | domain | Decimal sentinel | domain-internal |
| M210_NOT_YET_AUTHORED_SENTINEL | domain/calculations/registry/_formula_runtime.py:57 | domain | Decimal sentinel | domain-internal |
| M210_RATE_SENTINELS | domain/calculations/registry/_formula_runtime.py:58 | domain | frozenset | domain-internal |
| CENSUS_MODELO_SERVICE_OWNER | domain/calculations/registry/_censo_modelos.py:17 | domain | string | domain-internal |
| DEVENGADA_FLOW_DIRECTIONS | domain/iva/_flow.py:250 | domain | frozenset | domain/iva re-export |
| DEDUCIBLE_FLOW_DIRECTIONS | domain/iva/_flow.py:256 | domain | frozenset | domain/iva re-export |
| LEDGER_RENTA_EXPENSE_SOURCE | domain/renta/_ledger_expenses.py:28 | domain | string | domain-internal re-export |
| SCHEMA_VERSION (inventory) | domain/profile/inventory/__init__.py:34 | domain | string | domain-internal (DUPLICATE NAME) |
| SCHEMA_VERSION (assets) | domain/profile/assets/__init__.py:20 | domain | string | domain-internal (DUPLICATE NAME) |
| SPANISH_AMOUNT_GROUP | adapters/inbound/pdf/_label_regex.py:35 | adapter | regex pattern | adapters/inbound/borrador and declaracion |
| TEXT_VALUE_GROUP | adapters/inbound/pdf/_label_regex.py:52 | adapter | regex pattern | adapters/inbound/declaracion/_parser.py |
| SECURE_OBJECT_SCHEMA_VERSION_V1 | adapters/persistence/storage/_namespace_registry.py:14 | adapter | numeric | adapter-wide (all namespace defs) |
| BLOB_MANIFEST_SCHEMA_VERSION | adapters/persistence/storage/_namespace_registry.py:27 | adapter | numeric | adapters/persistence/storage/blob_store |
| SECRET_RECORD_SCHEMA_VERSION | adapters/persistence/storage/_namespace_registry.py:28 | adapter | numeric | adapters/persistence/storage/secret_store |
| USER_PROFILE_VALUE_NAMESPACE (NamespaceDef) | adapters/persistence/storage/_namespace_registry.py:221 | adapter | NamespaceDef | application/user_profile/_repository.py |
| USER_PROFILE_SNAPSHOT_NAMESPACE (NamespaceDef) | adapters/persistence/storage/_namespace_registry.py:230 | adapter | NamespaceDef | application/user_profile/_repository.py |
| USER_PROFILE_VALUE_NAMESPACE (str shadow) | application/user_profile/_repository.py:44 | application | string | application-internal (shadows adapter NamespaceDef) |
| USER_PROFILE_SNAPSHOT_NAMESPACE (str shadow) | application/user_profile/_repository.py:45 | application | string | application-internal (shadows adapter NamespaceDef) |
| IVA_COMPENSATION_WALLET_URL | adapters/outbound/aeat/sede/_iva_compensation_wallet.py:64 | adapter | URL | application/live/__init__.py |
| PRE303_PRESENTATION_SERVICE_URL | adapters/outbound/aeat/sede/_iva_compensation_wallet.py:65 | adapter | URL | application/live/__init__.py |
| REQUIRED_SCOPES | adapters/outbound/google/_records.py:36 | adapter | tuple | entrypoints/cli/_config/_google.py, adapters/outbound/storage/_factory.py |
| CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE | adapters/outbound/aeat/auth/_clave_movil.py:83 | adapter | string | application/auth/_diagnostics.py (indirect) |
| SUPPORTED_BUNDLE_SCHEMA_VERSIONS | application/user_profile/_bundle.py:33 | application | frozenset | entrypoints/cli/_config/__init__.py |
| MINIMUM_DISPLAY_ID_WIDTH | application/ledger/_id_resolution.py:26 | application | numeric | application-internal only |

---

### 2. Cross-layer coupling map (production code)

| Constant | Declared in | Imported by | Violation |
|---|---|---|---|
| M347_THRESHOLD_EUR | domain/modelos | entrypoints/cli | domain to entrypoint; statutory value should live in core |
| APPROVAL_BASIS_VERSION | domain/filing | application/filing | domain to application |
| TX_BUCKET_NAMESPACE | domain/transactions | application/ledger | domain to application; namespaces belong in storage registry |
| AEAT_GROI_URL | domain/calculations/registry | adapters/outbound/aeat/sede | TOML URL re-exposed in domain, consumed by adapter |
| AEAT_NIF_IVA_VERIFICATION_URL | domain/calculations/registry | adapters/outbound/aeat/sede | same pattern |
| AEAT_NIF_IVA_ENTRY_URL | domain/calculations/registry | adapters/outbound/aeat/sede | same pattern |
| IVA_COMPENSATION_WALLET_URL | adapters/outbound/aeat/sede | application/live | adapter to application; outward direction violation |
| PRE303_PRESENTATION_SERVICE_URL | adapters/outbound/aeat/sede | application/live | adapter to application; outward direction violation |
| USER_PROFILE_VALUE_NAMESPACE | adapters/persistence/storage | application/user_profile | adapter to application; outward direction violation |
| USER_PROFILE_SNAPSHOT_NAMESPACE | adapters/persistence/storage | application/user_profile | adapter to application; outward direction violation |
| PROJECT_ROOT | core/config.py AND core/paths.py | multiple layers | duplicate declaration; split import origin |

---

### 3. Misplaced cross-cutting constants

M347_THRESHOLD_EUR (Decimal 3005.06) at domain/modelos/_row_models.py:276 is a statutory
threshold (RD 1065/2007 art. 31.1) consumed by the entrypoint CLI layer. It should move to
a new core/statutory_thresholds.py so the entrypoint does not import domain.

AEAT_GROI_URL, AEAT_NIF_IVA_VERIFICATION_URL, AEAT_NIF_IVA_ENTRY_URL are TOML-backed AEAT
URLs constructed in domain oracle modules then imported by adapter scrapers. Adapters should
call Settings.external_constants().aeat.oracles.* directly. Oracle modules may keep private
underscore-prefixed copies but must not re-export them as module constants.

IVA_COMPENSATION_WALLET_URL and PRE303_PRESENTATION_SERVICE_URL at
adapters/outbound/aeat/sede/_iva_compensation_wallet.py:64-65 are imported by
application/live/__init__.py. Application must not import from outbound adapters.
Both URLs are derivable from Settings.external_constants().aeat.sede_paths.*

TX_BUCKET_NAMESPACE at domain/transactions/_repository.py:28 is consumed by
application/ledger/_actions.py. All namespace strings belong with the storage namespace
registry at adapters/persistence/storage/_namespace_registry.py. The domain repository
should receive the namespace as a constructor argument.

---

### 4. Duplicate / parallel declarations

PROJECT_ROOT is declared identically at core/config.py:60 and core/paths.py:23. Callers
import from either source. Canonical source: core/paths.py. core/config.py should
import from there.

_IVA_RATE_TO_VAT_KIND is declared in two domain modules with different coverage:
- domain/iva/_invoice_classification.py:63 -- 5 entries (RATE_0, RATE_4, RATE_10, RATE_21, EXEMPT)
- domain/invoices/_enums.py:76 -- 3 entries (RATE_4, RATE_10, RATE_21 only)

The invoices version omits RATE_0 and EXEMPT, creating a latent classification hole for
zero-rated and exempt lines. Canonical: domain/invoices/_enums.py expanded to 5 entries;
domain/iva/_invoice_classification.py imports from there and its private copy deleted.

SCHEMA_VERSION = 1 appears in both domain/profile/inventory/__init__.py:34 and
domain/profile/assets/__init__.py:20. Same name, same value, sibling modules. Not
cross-imported but ambiguous under grep. Rename to INVENTORY_SCHEMA_VERSION and
ASSETS_SCHEMA_VERSION respectively.

USER_PROFILE_VALUE_NAMESPACE exists as SecureObjectNamespaceDefinition at
adapters/persistence/storage/_namespace_registry.py:221 and as plain string at
application/user_profile/_repository.py:44. Same name, different types across adjacent
layers. The application-layer symbol should be renamed.

---

### 5. core/external_constants gap analysis

Already centralised (no action needed): all MIME types, file extensions, encoding constants,
DEFAULT_CURRENCY, CLASSIFIED_BY_MANUAL, PROVENANCE_SOURCE_MANUAL_CLI, and all AEAT external
URLs and OAuth scopes via the ExternalConstants TOML model.

Gaps -- cross-cutting constants absent from core:

| Gap | Current location | Action |
|---|---|---|
| M347_THRESHOLD_EUR | domain/modelos/_row_models.py:276 | Move to core/statutory_thresholds.py with BOE citation |
| APPROVAL_BASIS_VERSION | domain/filing/_schema.py:25 | Move to core/ if more consumers appear |
| TX_BUCKET_NAMESPACE | domain/transactions/_repository.py:28 | Move to adapters/persistence/storage/_namespace_registry.py |
| GROI_ORACLE_ID | domain/calculations/registry/_groi_oracle.py:60 | Move to external_constants.toml [aeat.oracles] or make private |
| AEAT_GROI_URL et al. | domain/calculations/registry | Remove module constants; callers read Settings.external_constants() |
| IVA_COMPENSATION_WALLET_URL etc. | adapters/outbound/aeat/sede | Remove module constants; application reads Settings.external_constants() |

---

### 6. Placement recommendations

| Constant | Current layer | Canonical location | Action |
|---|---|---|---|
| PROJECT_ROOT (config.py) | core/config.py | core/paths.py | Remove from config.py; import from paths |
| M347_THRESHOLD_EUR | domain/modelos | core/statutory_thresholds.py (new) | Relocate; add BOE citation |
| AEAT_GROI_URL | domain/calculations/registry | Remove; adapter reads Settings.external_constants() | Delete module constant |
| AEAT_NIF_IVA_* URLs | domain/calculations/registry | Remove; adapter reads Settings.external_constants() | Delete module constants |
| IVA_COMPENSATION_WALLET_URL, PRE303_PRESENTATION_SERVICE_URL | adapters/outbound/aeat/sede | Remove; application reads Settings.external_constants() | Delete; fix application/live import |
| TX_BUCKET_NAMESPACE | domain/transactions | adapters/persistence/storage/_namespace_registry.py | Relocate; domain receives namespace as constructor arg |
| _IVA_RATE_TO_VAT_KIND (dup) | domain/iva/_invoice_classification.py | domain/invoices/_enums.py expanded to 5 entries | Delete copy in _invoice_classification.py |
| SCHEMA_VERSION x2 | domain/profile submodules | Rename in-place | INVENTORY_SCHEMA_VERSION / ASSETS_SCHEMA_VERSION |
| APPROVAL_BASIS_VERSION | domain/filing | Keep domain-local; escalate if consumers grow | No immediate action |
| REQUIRED_SCOPES | adapters/outbound/google | Keep; entrypoint-to-adapter is valid | No action |
| SUPPORTED_BUNDLE_SCHEMA_VERSIONS | application/user_profile | Keep; entrypoint-to-application is valid | No action |
| SPANISH_AMOUNT_GROUP, TEXT_VALUE_GROUP | adapters/inbound/pdf | Keep; consumed only within adapters/inbound | No action |

---

## Module(s)

src/aeat/core/external_constants.py, src/aeat/core/paths.py, src/aeat/core/config.py, src/aeat/domain/modelos/_row_models.py, src/aeat/domain/filing/_schema.py, src/aeat/domain/transactions/_repository.py, src/aeat/domain/calculations/registry/_groi_oracle.py, src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py, src/aeat/domain/calculations/registry/_formula_runtime.py, src/aeat/domain/iva/_flow.py, src/aeat/domain/iva/_invoice_classification.py, src/aeat/domain/invoices/_enums.py, src/aeat/domain/profile/inventory/__init__.py, src/aeat/domain/profile/assets/__init__.py, src/aeat/adapters/persistence/storage/_namespace_registry.py, src/aeat/adapters/outbound/aeat/sede/_groi_check.py, src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py, src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py, src/aeat/adapters/outbound/google/_records.py, src/aeat/application/live/_censo.py, src/aeat/application/live/_borrador_100.py, src/aeat/application/user_profile/_repository.py, src/aeat/application/user_profile/_bundle.py, src/aeat/entrypoints/cli/_modelo.py

## File(s)

- src/aeat/core/external_constants.py:24-306 -- all existing centralised constants
- src/aeat/core/paths.py:23 -- canonical PROJECT_ROOT; duplicate in core/config.py:60 to eliminate
- src/aeat/domain/modelos/_row_models.py:276 -- M347_THRESHOLD_EUR; relocate to core
- src/aeat/domain/iva/_invoice_classification.py:63 -- duplicate _IVA_RATE_TO_VAT_KIND; delete
- src/aeat/domain/invoices/_enums.py:76 -- canonical _IVA_RATE_TO_VAT_KIND; expand to 5 entries
- src/aeat/adapters/persistence/storage/_namespace_registry.py:14-28 -- schema version integers
- src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py:64-65 -- URL constants to remove
- src/aeat/domain/calculations/registry/_groi_oracle.py:60-64 -- URL/ID constants; make private
- src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py:44-50 -- URL constants; make private

## Related

