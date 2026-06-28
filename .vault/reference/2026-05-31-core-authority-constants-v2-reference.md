---
tags:
  - '#reference'
  - '#core-authority-constants-v2'
date: '2026-05-31'
modified: '2026-05-31'
related: []
---

# core-authority-constants-v2 reference: AST constants audit

Mechanical AST-based exhaustive audit of every module-scope constant
across 1,655 .py files under src/aeat/. Extraction rules:
UPPER_SNAKE_CASE, _UPPER_SNAKE_CASE, lowercase names whose value is
a literal scalar, collection, Field(...), TypeAdapter(...), re.compile(),
frozen Mapping, or frozenset().

## Summary statistics

| Metric | Count |
| --- | --- |
| Total Python files scanned | 1,655 |
| Total constant declarations extracted | 2,435 |
| Files with at least one constant | 779 |
| UPPER_SNAKE_CASE constants | 333 |
| Cross-module constants (imported by >=1 other file) | 267 |
| Cross-layer coupling instances | 339 |
| Unique names in cross-layer coupling | 74 |
| Same-name multi-declarations | 193 names |
| Declarations in core/external_constants.py | 13 |
| Gap: cross-module constants NOT in external_constants | 259 |

## 1. Per-category inventory

### Decimal / numeric threshold constants
Count: 6

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `ART_23_1_F_RATE` | `aeat\domain\fincas\_amortization_ledger.py:30` | domain | ART_23_1_F_RATE: Decimal = Decimal("0.03") | 1 |
| `DAYS_PER_YEAR` | `aeat\domain\fincas\_amortization_ledger.py:33` | domain | DAYS_PER_YEAR: Decimal = Decimal("365") | 0 |
| `M347_THRESHOLD_EUR` | `aeat\domain\modelos\_row_models.py:276` | domain | M347_THRESHOLD_EUR: Decimal = Decimal("3005.06") | 3 |
| `PRIOR_RENT_REBAJA_THRESHOLD` | `aeat\domain\fincas\_tier_resolver.py:61` | domain | PRIOR_RENT_REBAJA_THRESHOLD: Decimal = Decimal("0.05") | 1 |
| `THRESHOLD_347_EUR` | `aeat\application\aggregation\_counterpart.py:311` | application | THRESHOLD_347_EUR: Decimal = Decimal("3005.06") | 1 |
| `THRESHOLD_720_EUR_PER_CLASS` | `aeat\application\aggregation\_foreign_assets.py:153` | application | THRESHOLD_720_EUR_PER_CLASS: Decimal = Decimal("50000.0 | 1 |

### String constants (UPPER_SNAKE_CASE)
Count: 71 — showing all

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `ALL_TOKEN` | `aeat\domain\auth\apoderamientos\_catalogue.py:15` | domain | ALL_TOKEN = "ALL" | 2 |
| `APPROVAL_BASIS_VERSION` | `aeat\domain\filing\_schema.py:25` | domain | APPROVAL_BASIS_VERSION = "review-basis-v1" | 2 |
| `ASSETS_AMORTIZATION_LEDGER_FILENAME` | `aeat\adapters\persistence\profile\assets.py:27` | adapters | ASSETS_AMORTIZATION_LEDGER_FILENAME = "assets-amortizat | 0 |
| `ASSETS_LEDGER_FILENAME` | `aeat\adapters\persistence\profile\assets.py:26` | adapters | ASSETS_LEDGER_FILENAME = "assets-ledger.secure-object" | 0 |
| `BINARY_MIME_TYPE` | `aeat\core\external_constants.py:27` | core | BINARY_MIME_TYPE: Final[str] = "application/octet-strea | 2 |
| `BUCKETS_DIRNAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:19` | adapters | BUCKETS_DIRNAME = "buckets" | 8 |
| `BUCKET_AUDIT_DIRNAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:22` | adapters | BUCKET_AUDIT_DIRNAME = "audit" | 2 |
| `BUCKET_BLOBS_DIRNAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:21` | adapters | BUCKET_BLOBS_DIRNAME = "blobs" | 2 |
| `BUCKET_DB_DIRNAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:20` | adapters | BUCKET_DB_DIRNAME = "db" | 5 |
| `BUCKET_DEK_FILENAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:26` | adapters | BUCKET_DEK_FILENAME = "bucket.dek.json" | 3 |
| `BUCKET_LOCK_FILENAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:24` | adapters | BUCKET_LOCK_FILENAME = ".lock" | 3 |
| `BUCKET_MANIFEST_FILENAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:23` | adapters | BUCKET_MANIFEST_FILENAME = "manifest.toml" | 3 |
| `CENSUS_MODELO_SERVICE_OWNER` | `aeat\domain\calculations\registry\_censo_modelos.py:17` | domain | CENSUS_MODELO_SERVICE_OWNER = "aeat.domain.calculations | 2 |
| `CENSUS_SOURCE_TAG` | `aeat\application\user_profile\_censo_sync.py:52` | application | CENSUS_SOURCE_TAG: Final = "aeat_census_read" | 2 |
| `CERTIFICATE_CONTEXT_MARKER` | `aeat\adapters\outbound\aeat\auth\_certificate_backends\_base.py:18` | adapters | CERTIFICATE_CONTEXT_MARKER = "_aeat_certificate_thumbpr | 7 |
| `CLASSIFIED_BY_MANUAL` | `aeat\core\external_constants.py:38` | core | CLASSIFIED_BY_MANUAL: Final[str] = "manual" | 7 |
| `CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE` | `aeat\adapters\outbound\aeat\auth\_clave_movil.py:83` | adapters | CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE: Final[str] = "aeat.ou | 4 |
| `CLI_BUCKET_ID_PLACEHOLDER` | `aeat\core\redaction\__init__.py:88` | core | CLI_BUCKET_ID_PLACEHOLDER = "<bucket-id>" | 3 |
| `CLI_OBJECT_KEY_PLACEHOLDER` | `aeat\core\redaction\__init__.py:89` | core | CLI_OBJECT_KEY_PLACEHOLDER = "<object-key>" | 3 |
| `CLI_PROFILE_ID_PLACEHOLDER` | `aeat\core\redaction\__init__.py:87` | core | CLI_PROFILE_ID_PLACEHOLDER = "<profile-id>" | 4 |
| `CSV_MIME_TYPE` | `aeat\core\external_constants.py:33` | core | CSV_MIME_TYPE: Final[str] = "text/csv" | 1 |
| `DEFAULT_CURRENCY` | `aeat\core\external_constants.py:24` | core | DEFAULT_CURRENCY: Final[str] = "EUR" | 16 |
| `DEFAULT_OUTPUT_LANGUAGE` | `aeat\core\i18n\_render.py:28` | core | DEFAULT_OUTPUT_LANGUAGE: Final[str] = "es" | 2 |
| `DEV_TEST_DATABASE_PASSWORD` | `aeat\core\config.py:61` | core | DEV_TEST_DATABASE_PASSWORD = "aeat-dev-test-database-pa | 0 |
| `DEV_TEST_DATABASE_PASSWORD_ENV_VAR` | `aeat\core\config.py:63` | core | DEV_TEST_DATABASE_PASSWORD_ENV_VAR = "AEAT_DEV_TEST_DAT | 0 |
| `GROI_ORACLE_ID` | `aeat\domain\calculations\registry\_groi_oracle.py:60` | domain | GROI_ORACLE_ID = "aeat-groi-spanish-roi-checker" | 6 |
| `HEADER_FONT` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:34` | tests | HEADER_FONT = "Helvetica-Bold" | 0 |
| `INVENTORY_LEDGER_FILENAME` | `aeat\adapters\persistence\profile\inventory.py:26` | adapters | INVENTORY_LEDGER_FILENAME = "inventory-ledger.secure-ob | 0 |
| `JSON_MIME_TYPE` | `aeat\core\external_constants.py:30` | core | JSON_MIME_TYPE: Final[str] = "application/json" | 1 |
| `KEYRING_SERVICE` | `aeat\adapters\persistence\storage\master_key\_master_key.py:120` | adapters | KEYRING_SERVICE: Final[str] = "aeat:secure-persistence" | 0 |
| `KEYRING_USERNAME` | `aeat\adapters\persistence\storage\master_key\_master_key.py:123` | adapters | KEYRING_USERNAME: Final[str] = "master" | 1 |
| `KEYSTORE_DIRNAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:25` | adapters | KEYSTORE_DIRNAME = "keystore" | 2 |
| `LABEL_FONT` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:36` | tests | LABEL_FONT = "Helvetica" | 1 |
| `LATIN_1_ENCODING` | `aeat\core\external_constants.py:301` | core | LATIN_1_ENCODING: Final[str] = "latin-1" | 0 |
| `LEDGER_RENTA_EXPENSE_SOURCE` | `aeat\domain\renta\_ledger_expenses.py:28` | domain | LEDGER_RENTA_EXPENSE_SOURCE = "ledger_renta_expense_agg | 2 |
| `LIVE_OPT_IN_ENV` | `aeat\tests\conftest.py:57` | tests | LIVE_OPT_IN_ENV: str = "AEAT_LIVE_TESTS_ENABLED" | 0 |
| `ORACLE_ID` | `aeat\domain\calculations\registry\_aeat_nif_iva_oracle.py:41` | domain | ORACLE_ID = "aeat-nif-iva-checker" | 5 |
| `OUTPUT_LANGUAGE_ENV_VAR` | `aeat\core\i18n\_render.py:27` | core | OUTPUT_LANGUAGE_ENV_VAR: Final[str] = "AEAT_OUTPUT_LANG | 3 |
| `OUTSIDE_PERIOD` | `aeat\application\aggregation\_shared_issue_reasons.py:31` | application | OUTSIDE_PERIOD: Final[str] = "outside_period" | 0 |
| `PASSPHRASE_ENV_VAR` | `aeat\adapters\persistence\storage\master_key\_master_key.py:126` | adapters | PASSPHRASE_ENV_VAR: Final[str] = "AEAT_SECRET_PASSPHRAS | 0 |
| `PDF_EXTENSION` | `aeat\core\external_constants.py:289` | core | PDF_EXTENSION: Final[str] = ".pdf" | 5 |
| `PDF_MIME_TYPE` | `aeat\core\external_constants.py:286` | core | PDF_MIME_TYPE: Final[str] = "application/pdf" | 0 |
| `PERSONAL_TRANSACTION` | `aeat\application\aggregation\_shared_issue_reasons.py:30` | application | PERSONAL_TRANSACTION: Final[str] = "personal_transactio | 0 |
| `PLAYWRIGHT_WAIT_DOMCONTENTLOADED` | `aeat\adapters\outbound\aeat\sede\_browser_constants.py:15` | adapters | PLAYWRIGHT_WAIT_DOMCONTENTLOADED: Final[str] = "domcont | 2 |
| `PLAYWRIGHT_WAIT_NETWORKIDLE` | `aeat\adapters\outbound\aeat\sede\_browser_constants.py:19` | adapters | PLAYWRIGHT_WAIT_NETWORKIDLE: Final[str] = "networkidle" | 2 |
| `PROVENANCE_SOURCE_MANUAL_CLI` | `aeat\core\external_constants.py:306` | core | PROVENANCE_SOURCE_MANUAL_CLI: Final[str] = "manual_cli" | 0 |
| `REMOTE_MIRROR_MANIFEST_NAMESPACE` | `aeat\adapters\outbound\storage\_mirror_manifest.py:20` | adapters | REMOTE_MIRROR_MANIFEST_NAMESPACE = "_sync-state" | 3 |
| `RENTA_WEB_OPEN_ORACLE_ID` | `aeat\domain\calculations\registry\test_live_parity_audit.py:48` | domain | RENTA_WEB_OPEN_ORACLE_ID = "modelo-100-renta-web-open" | 0 |
| `REPLAY_ACTIVE_ENV_VAR` | `aeat\core\observability\_replay.py:26` | core | REPLAY_ACTIVE_ENV_VAR = "AEAT_REPLAY_ACTIVE" | 2 |
| `SANITIZER_VERSION` | `aeat\adapters\inbound\sanitizer\_pipeline.py:63` | adapters | SANITIZER_VERSION = "0.1.0" | 1 |
| `SCHEMA_VERSION` | `aeat\domain\profile\assets\__init__.py:20` | domain | SCHEMA_VERSION = "1" | 0 |
| `SCHEMA_VERSION` | `aeat\domain\profile\inventory\__init__.py:34` | domain | SCHEMA_VERSION = "1" | 0 |
| `SCRUB_VERSION` | `aeat\adapters\inbound\pdf\_scrub.py:47` | adapters | SCRUB_VERSION = "1.0.0" | 1 |
| `SECRET_PASSPHRASE` | `aeat\adapters\outbound\aeat\auth\test_authenticator.py:60` | adapters | SECRET_PASSPHRASE = "correct-horse-battery-staple" | 0 |
| `SECRET_PASSPHRASE` | `aeat\adapters\outbound\aeat\auth\test_certificate.py:41` | adapters | SECRET_PASSPHRASE = "correct-horse-battery-staple" | 0 |
| `SECURE_OBJECT_CATALOGUE_KEY` | `aeat\adapters\persistence\storage\_namespace_registry.py:15` | adapters | SECURE_OBJECT_CATALOGUE_KEY = "catalogue" | 2 |
| `SECURE_OBJECT_DEFAULT_KEY` | `aeat\adapters\persistence\storage\_namespace_registry.py:16` | adapters | SECURE_OBJECT_DEFAULT_KEY = "default" | 2 |
| `SECURE_OBJECT_WORKFLOW_STATE_KEY` | `aeat\adapters\persistence\storage\_namespace_registry.py:17` | adapters | SECURE_OBJECT_WORKFLOW_STATE_KEY = "state" | 2 |
| `SEDE_BODY_ENCODING` | `aeat\adapters\outbound\aeat\sede\_browser_constants.py:28` | adapters | SEDE_BODY_ENCODING: Final[str] = "latin-1" | 0 |
| `SPANISH_AMOUNT_GROUP` | `aeat\adapters\inbound\pdf\_label_regex.py:35` | adapters | SPANISH_AMOUNT_GROUP = r"(-?0-9]{1,3}(?:[.  ]0-9]{3}) | 4 |
| `SYSTEM_BUCKET_ID` | `aeat\application\workflow\_events.py:27` | application | SYSTEM_BUCKET_ID: Final[str] = "system" | 0 |
| `TEXT_VALUE_GROUP` | `aeat\adapters\inbound\pdf\_label_regex.py:52` | adapters | TEXT_VALUE_GROUP = r"(\S+?)\s*$" | 1 |
| `TX_BUCKET_NAMESPACE` | `aeat\domain\transactions\_repository.py:28` | domain | TX_BUCKET_NAMESPACE = "aeat.domain.transactions.bucket" | 4 |
| `UNCLASSIFIED_BUSINESS_STATE` | `aeat\application\aggregation\_shared_issue_reasons.py:29` | application | UNCLASSIFIED_BUSINESS_STATE: Final[str] = "unclassified | 0 |
| `UNSUPPORTED_CURRENCY` | `aeat\application\aggregation\_shared_issue_reasons.py:28` | application | UNSUPPORTED_CURRENCY: Final[str] = "unsupported_currenc | 0 |
| `UNSUPPORTED_DIRECTION` | `aeat\application\aggregation\_shared_issue_reasons.py:27` | application | UNSUPPORTED_DIRECTION: Final[str] = "unsupported_direct | 0 |
| `VALUE_FONT` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:38` | tests | VALUE_FONT = "Helvetica" | 0 |
| `WORKFLOW_STATE_OBJECT_ID` | `aeat\application\workflow\_events.py:28` | application | WORKFLOW_STATE_OBJECT_ID: Final[str] = "aeat.workflow:s | 0 |
| `XLSM_EXTENSION` | `aeat\core\external_constants.py:298` | core | XLSM_EXTENSION: Final[Literal[".xlsm"]] = ".xlsm" | 0 |
| `XLSX_EXTENSION` | `aeat\core\external_constants.py:295` | core | XLSX_EXTENSION: Final[Literal[".xlsx"]] = ".xlsx" | 4 |
| `XLS_EXTENSION` | `aeat\core\external_constants.py:292` | core | XLS_EXTENSION: Final[Literal[".xls"]] = ".xls" | 0 |

### Integer constants (UPPER_SNAKE_CASE)
Count: 23

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION` | `aeat\adapters\outbound\aeat\auth\_clave_movil.py:80` | adapters | AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION: Final[int] =  | 0 |
| `AEAT_STORAGE_STATE_SCHEMA_VERSION` | `aeat\adapters\outbound\aeat\auth\_authenticator.py:98` | adapters | AEAT_STORAGE_STATE_SCHEMA_VERSION: Final[int] = 1 | 0 |
| `BLOB_MANIFEST_SCHEMA_VERSION` | `aeat\adapters\persistence\storage\_namespace_registry.py:27` | adapters | BLOB_MANIFEST_SCHEMA_VERSION = 1 | 3 |
| `CARRY_FORWARD_MAX_YEARS` | `aeat\domain\fincas\_expense_rollup.py:29` | domain | CARRY_FORWARD_MAX_YEARS: int = 4 | 1 |
| `DEFAULT_EJERCICIO_AMENDMENT_YEAR` | `aeat\domain\fincas\_tier_resolver.py:51` | domain | DEFAULT_EJERCICIO_AMENDMENT_YEAR: int = 2024 | 2 |
| `FILING_YEAR` | `aeat\domain\profile\test_custodia_compartida.py:30` | domain | FILING_YEAR = 2024 | 0 |
| `FILING_YEAR` | `aeat\domain\profile\test_descendant_info.py:35` | domain | FILING_YEAR = 2024 | 0 |
| `FILING_YEAR` | `aeat\domain\profile\test_marriage_facts.py:30` | domain | FILING_YEAR = 2024 | 0 |
| `GCM_TAG_SIZE` | `aeat\adapters\persistence\storage\crypto\_crypto.py:35` | adapters | GCM_TAG_SIZE: int = 16 | 3 |
| `HEADER_FONT_SIZE` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:35` | tests | HEADER_FONT_SIZE = 12 | 0 |
| `JOVEN_TENANT_AGE_MAX` | `aeat\domain\fincas\_tier_resolver.py:67` | domain | JOVEN_TENANT_AGE_MAX: int = 35 | 1 |
| `JOVEN_TENANT_AGE_MIN` | `aeat\domain\fincas\_tier_resolver.py:66` | domain | JOVEN_TENANT_AGE_MIN: int = 18 | 1 |
| `KEY_SIZE` | `aeat\adapters\persistence\storage\crypto\_crypto.py:38` | adapters | KEY_SIZE: int = 32 | 11 |
| `LABEL_FONT_SIZE` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:37` | tests | LABEL_FONT_SIZE = 9 | 1 |
| `MINIMUM_DISPLAY_ID_WIDTH` | `aeat\application\ledger\_id_resolution.py:26` | application | MINIMUM_DISPLAY_ID_WIDTH = 8 | 2 |
| `NIST_PASSPHRASE_MIN_LENGTH` | `aeat\adapters\persistence\storage\master_key\_master_key.py:84` | adapters | NIST_PASSPHRASE_MIN_LENGTH: Final[int] = 8 | 0 |
| `NONCE_SIZE` | `aeat\adapters\persistence\storage\crypto\_crypto.py:32` | adapters | NONCE_SIZE: int = 12 | 3 |
| `PLAYWRIGHT_TIMEOUT_SHORT_MS` | `aeat\adapters\outbound\aeat\sede\_browser_constants.py:23` | adapters | PLAYWRIGHT_TIMEOUT_SHORT_MS: Final[int] = 2_000 | 0 |
| `REHAB_LOOKBACK_DAYS` | `aeat\domain\fincas\_tier_resolver.py:55` | domain | REHAB_LOOKBACK_DAYS: int = 730 | 1 |
| `REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION` | `aeat\adapters\outbound\storage\_mirror_manifest.py:21` | adapters | REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION = 1 | 1 |
| `SECRET_RECORD_SCHEMA_VERSION` | `aeat\adapters\persistence\storage\_namespace_registry.py:28` | adapters | SECRET_RECORD_SCHEMA_VERSION = 1 | 2 |
| `SECURE_OBJECT_SCHEMA_VERSION_V1` | `aeat\adapters\persistence\storage\_namespace_registry.py:14` | adapters | SECURE_OBJECT_SCHEMA_VERSION_V1 = 1 | 1 |
| `VALUE_FONT_SIZE` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:39` | tests | VALUE_FONT_SIZE = 10 | 0 |

### Tuple / frozenset / set literal constants (UPPER_SNAKE_CASE)
Count: 57

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `ACCEPTED_ROOTS` | `aeat\application\operator_surface\_contract.py:29` | application | ACCEPTED_ROOTS: tuple[RootSurface, ...] = (     RootSur | 1 |
| `ACCEPTED_SOURCE_KINDS` | `aeat\application\aggregation\_service.py:49` | application | ACCEPTED_SOURCE_KINDS: tuple[AggregationSourceKind, ... | 3 |
| `AEAT_WRITE_FORBIDDEN_ACTIONS` | `aeat\domain\calculations\registry\_remote_state_guard.py:36` | domain | AEAT_WRITE_FORBIDDEN_ACTIONS: tuple[str, ...] = (     " | 6 |
| `AEAT_WRITE_FORBIDDEN_VERB_TOKENS` | `aeat\domain\calculations\registry\_remote_state_guard.py:70` | domain | AEAT_WRITE_FORBIDDEN_VERB_TOKENS: frozenset[str] = froz | 4 |
| `ALLOWED_CLICK_OVERRIDES` | `aeat\adapters\outbound\aeat\sede\_renta_web_open_safety.py:103` | adapters | ALLOWED_CLICK_OVERRIDES: frozenset[str] = frozenset() | 1 |
| `AUTH_DIAGNOSTIC_PHONE_STATES` | `aeat\application\auth\_diagnostics.py:22` | application | AUTH_DIAGNOSTIC_PHONE_STATES: tuple[str, ...] = (     " | 2 |
| `AUTH_PROVIDER_CATALOGUE` | `aeat\application\auth\_catalogue.py:36` | application | AUTH_PROVIDER_CATALOGUE: tuple[AuthProviderListing, ... | 2 |
| `BANNED_LIVE_IMPORTS` | `aeat\tests\conftest.py:40` | tests | BANNED_LIVE_IMPORTS: frozenset[str] = frozenset(     {  | 0 |
| `BOOTSTRAP_EXEMPT_VERB_PATHS` | `aeat\entrypoints\cli\_bootstrap_exempt.py:35` | entrypoints | BOOTSTRAP_EXEMPT_VERB_PATHS: tuple[str, ...] = (     #  | 0 |
| `BULK_CLASSIFY_ALLOWED_COLUMNS` | `aeat\application\ledger\_models.py:720` | application | BULK_CLASSIFY_ALLOWED_COLUMNS: frozenset[str] = frozens | 2 |
| `CANONICAL_CRUD_VERBS` | `aeat\application\operator_surface\_crud_contract.py:37` | application | CANONICAL_CRUD_VERBS: frozenset[CrudVerb] = frozenset(C | 3 |
| `CANONICAL_LAYOUT_PACKAGES` | `aeat\tests\test_layout_import_smoke.py:23` | tests | CANONICAL_LAYOUT_PACKAGES: tuple[str, ...] = (     "aea | 0 |
| `CANONICAL_PUBLIC_SYMBOLS` | `aeat\tests\test_layout_import_smoke.py:89` | tests | CANONICAL_PUBLIC_SYMBOLS: tuple[tuple[str, str], ...] = | 0 |
| `CAPPED_CATEGORIES` | `aeat\domain\fincas\_expense_rollup.py:32` | domain | CAPPED_CATEGORIES: frozenset[ExpenseCategory] = frozens | 1 |
| `CENSUS_DERIVED_FIELDS` | `aeat\domain\user_profile\test_census_schema_fields.py:16` | domain | CENSUS_DERIVED_FIELDS: tuple[tuple[str, str], ...] = (  | 0 |
| `CENSUS_MODELO_ERROR_CODES` | `aeat\domain\calculations\registry\_censo_modelos.py:19` | domain | CENSUS_MODELO_ERROR_CODES: tuple[str, ...] = ("ERROR_CA | 2 |
| `CENSUS_MODELO_EVENT_KINDS` | `aeat\domain\calculations\registry\_censo_modelos.py:18` | domain | CENSUS_MODELO_EVENT_KINDS: tuple[str, ...] = ("alta", " | 2 |
| `CLASSIFIED_STATES` | `aeat\domain\transactions\_enums.py:107` | domain | CLASSIFIED_STATES: frozenset[BusinessClassification] =  | 1 |
| `COUNTERPART_BINDING_SOURCE_KINDS` | `aeat\domain\calculations\registry\_bindings.py:1636` | domain | COUNTERPART_BINDING_SOURCE_KINDS: frozenset[Counterpart | 0 |
| `COVERAGE_GAPS` | `aeat\test_coverage_inventory.py:58` | test_coverage_inventory.py | COVERAGE_GAPS: frozenset[str] = frozenset(     {        | 0 |
| `CSV_ENCODING_FALLBACK_CHAIN` | `aeat\core\external_constants.py:303` | core | CSV_ENCODING_FALLBACK_CHAIN: tuple[str, ...] = ("utf-8- | 2 |
| `CSV_EXTENSIONS` | `aeat\adapters\inbound\financial\providers\_constants.py:21` | adapters | CSV_EXTENSIONS: frozenset[str] = frozenset({".csv", ".t | 3 |
| `CSV_LAYOUTS` | `aeat\adapters\inbound\financial\providers\_csv.py:158` | adapters | CSV_LAYOUTS: tuple[CsvBankLayout, ...] = (     N26_LAYO | 1 |
| `DECIMAL_STR_PENDING` | `aeat\test_decimal_enrollment_inventory.py:55` | test_decimal_enrollment_inventory.py | DECIMAL_STR_PENDING: frozenset[str] = frozenset(     {  | 0 |
| `DOMAIN_NAMESPACE_DEFINITIONS` | `aeat\adapters\persistence\storage\_namespace_registry.py:548` | adapters | DOMAIN_NAMESPACE_DEFINITIONS = (     SecureObjectNamesp | 1 |
| `ERROR_CODES` | `aeat\application\aggregation\_service.py:56` | application | ERROR_CODES: tuple[str, ...] = (     "ERROR_FINANCIAL_A | 2 |
| `ERROR_CODES` | `aeat\application\operator_surface\_contract.py:332` | application | ERROR_CODES: tuple[str, ...] = ("REFUSED_OPERATOR_SURFA | 2 |
| `EU_MEMBER_STATE_CODES` | `aeat\domain\invoices\_validators.py:36` | domain | EU_MEMBER_STATE_CODES: frozenset[str] = frozenset(membe | 1 |
| `EXPECTED_LEDGER_VERBS` | `aeat\entrypoints\cli\test_ledger_verb_spine.py:24` | entrypoints | EXPECTED_LEDGER_VERBS: frozenset[str] = frozenset(      | 0 |
| `EXPECTED_OVERVIEW_VERBS` | `aeat\entrypoints\cli\test_overview_explain_verb.py:22` | entrypoints | EXPECTED_OVERVIEW_VERBS: frozenset[str] = frozenset(    | 0 |
| `FORBIDDEN_URL_FRAGMENTS` | `aeat\adapters\outbound\aeat\sede\_renta_web_open_safety.py:86` | adapters | FORBIDDEN_URL_FRAGMENTS: frozenset[str] = frozenset(    | 1 |
| `INVOICE_BINDING_SOURCE_KINDS` | `aeat\domain\calculations\registry\_bindings.py:32` | domain | INVOICE_BINDING_SOURCE_KINDS: frozenset[str] = frozense | 0 |
| `KNOWN_VERIFICATION_PREDICATE_OPERATORS` | `aeat\domain\calculations\registry\_schema.py:2382` | domain | KNOWN_VERIFICATION_PREDICATE_OPERATORS: frozenset[str]  | 3 |
| `LINK_CHECK_PREFLIGHT` | `aeat\entrypoints\cli\test_ledger_verb_spine.py:52` | entrypoints | LINK_CHECK_PREFLIGHT: frozenset[str] = frozenset({"link | 0 |
| `LIVE_ACCESS_MARKERS` | `aeat\tests\conftest.py:37` | tests | LIVE_ACCESS_MARKERS: frozenset[str] = frozenset({"live_ | 0 |
| `MIGRATED_COMMANDS` | `aeat\entrypoints\cli\test_json_schema_conformance.py:53` | entrypoints | MIGRATED_COMMANDS: frozenset[str] = frozenset(     {    | 0 |
| `MODELOS_WITHOUT_SHIFT` | `aeat\domain\deadlines\_festivos.py:187` | domain | MODELOS_WITHOUT_SHIFT: tuple[str, ...] = ("369",) | 2 |
| `MOUNTED_COMMAND_FAMILIES` | `aeat\application\operator_surface\_contract.py:174` | application | MOUNTED_COMMAND_FAMILIES: tuple[MountedCommandFamily, . | 1 |
| `PART_SPECS` | `aeat\domain\manuals\_fetch.py:61` | domain | PART_SPECS: tuple[PartSpec, ...] = (     PartSpec(      | 2 |
| `PENDING_ENROLLMENT` | `aeat\test_clock_enrollment_inventory.py:79` | test_clock_enrollment_inventory.py | PENDING_ENROLLMENT: frozenset[str] = frozenset(     {   | 0 |
| `PIPELINE_ONLY_CLASSIFICATIONS` | `aeat\domain\transactions\_llm.py:138` | domain | PIPELINE_ONLY_CLASSIFICATIONS: frozenset[BusinessClassi | 1 |
| `PROFILE_BOUND_WRITE_VERB_PATHS` | `aeat\application\storage_write_policy.py:49` | application | PROFILE_BOUND_WRITE_VERB_PATHS: tuple[str, ...] = (     | 0 |
| `REQUIRED_RELOCATED_PATHS` | `aeat\tests\test_layout_import_smoke.py:101` | tests | REQUIRED_RELOCATED_PATHS: tuple[str, ...] = (     "appl | 0 |
| `REQUIRED_SCOPES` | `aeat\adapters\outbound\google\_records.py:36` | adapters | REQUIRED_SCOPES: tuple[str, ...] = (OPENID_SCOPE, EMAIL | 9 |
| `RETIRED_OPERATOR_SURFACES` | `aeat\application\operator_surface\_contract.py:46` | application | RETIRED_OPERATOR_SURFACES: tuple[RetiredOperatorSurface | 1 |
| `RUNTIME_SURFACES` | `aeat\entrypoints\cli\test_retired_cli_literals.py:10` | entrypoints | RUNTIME_SURFACES = (     PROJECT_ROOT / "src" / "aeat", | 0 |
| `SANITIZED_SHAS` | `aeat\adapters\inbound\sanitizer\fixtures.py:23` | adapters | SANITIZED_SHAS: frozenset[str] = frozenset(     {       | 0 |
| `SCRUB_FIELD_PATTERNS` | `aeat\core\logging.py:36` | core | SCRUB_FIELD_PATTERNS: tuple[str, ...] = (     "access_t | 0 |
| `SERVICE_OWNERS` | `aeat\application\operator_surface\_contract.py:296` | application | SERVICE_OWNERS: tuple[ServiceOwner, ...] = (     Servic | 0 |
| `SOURCE_KINDS` | `aeat\application\operator_surface\_contract.py:160` | application | SOURCE_KINDS: tuple[SourceKind, ...] = (     SourceKind | 0 |
| `SOURCE_KIND_ALIASES` | `aeat\application\operator_surface\_contract.py:167` | application | SOURCE_KIND_ALIASES: tuple[SourceKindAlias, ...] = (    | 1 |
| `STORAGE_PATH_DEFINITIONS` | `aeat\adapters\persistence\storage\_namespace_registry.py:665` | adapters | STORAGE_PATH_DEFINITIONS = (     StoragePathDefinition( | 1 |
| `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` | `aeat\application\user_profile\_bundle.py:33` | application | SUPPORTED_BUNDLE_SCHEMA_VERSIONS: frozenset[int] = froz | 1 |
| `SUPPORTED_OUTPUT_LANGUAGES` | `aeat\core\i18n\_render.py:29` | core | SUPPORTED_OUTPUT_LANGUAGES: tuple[str, ...] = ("es", "e | 12 |
| `TEXT_SUFFIXES` | `aeat\entrypoints\cli\test_retired_cli_literals.py:14` | entrypoints | TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".example"} | 0 |
| `UE_EEA_COUNTRY_CODES` | `aeat\domain\profile\_renta_codes.py:50` | domain | UE_EEA_COUNTRY_CODES: frozenset[str] = frozenset({      | 1 |
| `WIZARD_FLOWS` | `aeat\application\wizard\_catalogue.py:857` | application | WIZARD_FLOWS: tuple[WizardFlow, ...] = (SETUP_FLOW,) | 5 |

### Dict literal constants (UPPER_SNAKE_CASE)
Count: 4

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `CATEGORY_FAMILY_MEMBERS` | `aeat\domain\categories\_spending_category.py:101` | domain | CATEGORY_FAMILY_MEMBERS: dict[SpendingCategoryFamily, t | 3 |
| `ENCODING_ALIAS_MAP` | `aeat\domain\calculations\registry\_record_spec.py:15` | domain | ENCODING_ALIAS_MAP: Mapping[str, str] = {     "latin-1" | 2 |
| `FIRST_SLICE_EXPENSE_CASILLAS` | `aeat\domain\renta\_first_slice_routing.py:26` | domain | FIRST_SLICE_EXPENSE_CASILLAS: Mapping[SpendingCategory, | 2 |
| `SCHEMA_REGISTRY` | `aeat\core\json_contract.py:102` | core | SCHEMA_REGISTRY: dict[str, RegisteredSchema] = {} | 2 |

### re.compile constants (all casing)
Count: 202

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `_A1_COLUMN` | `aeat\application\storage\calc_sheets\_records.py:76` | application | _A1_COLUMN = re.compile(r"^[A-Z]{1,3}$") | 0 |
| `_AEAT_KEY_PATTERN` | `aeat\core\test_settings_single_surface_invariant.py:52` | core | _AEAT_KEY_PATTERN: re.Pattern[str] = re.compile(r"^AEAT | 0 |
| `_AMOUNT_RE` | `aeat\adapters\inbound\pdf\_scrub.py:52` | adapters | _AMOUNT_RE = re.compile(r"\b(?P<whole>0-9]{1,3}(?:\.[0 | 0 |
| `_ANNUAL_PERIOD_RE` | `aeat\domain\period.py:52` | domain | _ANNUAL_PERIOD_RE = re.compile(r"^(?P<year>\d{4})A$") | 0 |
| `_ANNUAL_RE` | `aeat\application\filing\_import.py:39` | application | _ANNUAL_RE = re.compile(r"^0A$") | 0 |
| `_ANNUAL_RE` | `aeat\application\filing\reconciliation\_reconcile.py:68` | application | _ANNUAL_RE: Final[re.Pattern[str]] = re.compile(r"^(?P< | 0 |
| `_ANNUAL_TOKEN_RE` | `aeat\application\filing\_testing_registry.py:109` | application | _ANNUAL_TOKEN_RE = re.compile(r"^0A$") | 0 |
| `_BARE_NUMERIC_RE` | `aeat\entrypoints\cli\_modelo.py:94` | entrypoints | _BARE_NUMERIC_RE = re.compile(r"^\d+$") | 0 |
| `_BARE_PERIOD_RE` | `aeat\domain\calculations\registry\_queries.py:32` | domain | _BARE_PERIOD_RE = re.compile(     r"^(?:0AI[1-4]TI[1-4] | 0 |
| `_BARE_YEAR_RE` | `aeat\domain\period.py:53` | domain | _BARE_YEAR_RE = re.compile(r"^\d{4}$") | 0 |
| `_BEARER_TOKEN_RE` | `aeat\core\logging.py:71` | core | _BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0 | 0 |
| `_BIC_RE` | `aeat\domain\calculations\registry\_schema.py:470` | domain | _BIC_RE = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3} | 0 |
| `_BORRADOR_RE` | `aeat\adapters\inbound\borrador\_detect.py:18` | adapters | _BORRADOR_RE = re.compile(r"\bBORRADOR\b", re.IGNORECAS | 0 |
| `_CADASTRAL_RE` | `aeat\adapters\outbound\aeat\sede\_censo.py:49` | adapters | _CADASTRAL_RE: Final = re.compile(r"^0-9A-Z]{20}$") | 0 |
| `_CANONICAL_ANNUAL_RE` | `aeat\application\filing\_import.py:43` | application | _CANONICAL_ANNUAL_RE = re.compile(r"^\d{4}A$") | 0 |
| `_CANONICAL_MONTH_RE` | `aeat\application\filing\_import.py:42` | application | _CANONICAL_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]I1[0-2 | 0 |
| `_CANONICAL_MONTH_RE` | `aeat\application\filing\reconciliation\_reconcile.py:67` | application | _CANONICAL_MONTH_RE: Final[re.Pattern[str]] = re.compil | 0 |
| `_CANONICAL_QUARTER_RE` | `aeat\application\filing\_import.py:41` | application | _CANONICAL_QUARTER_RE = re.compile(r"^\d{4}Q[1-4]$") | 0 |
| `_CASILLA_EDIT_RE` | `aeat\application\review\_edit.py:50` | application | _CASILLA_EDIT_RE = re.compile(r"^casilla\.(?P<casilla_i | 0 |
| `_CASILLA_TAG_RE` | `aeat\domain\calculations\registry\_record_design.py:1242` | domain | _CASILLA_TAG_RE = re.compile(r"\[(\d{5})\]") | 0 |
| `_CASILLA_VALUE_RE` | `aeat\adapters\inbound\borrador\_extractors\modelo_100_summary_v2025.py:24` | adapters | _CASILLA_VALUE_RE = re.compile(     rf"(?m)^\s*(?P<casi | 0 |
| `_CELL_REF_PATTERN` | `aeat\domain\calculations\registry\_workbook_parity.py:67` | domain | _CELL_REF_PATTERN = re.compile(r"(?<![A-Z0-9_])(?:'[^'] | 0 |
| `_CELL_REF_VALUE_PATTERN` | `aeat\domain\calculations\registry\_workbook_parity.py:68` | domain | _CELL_REF_VALUE_PATTERN = re.compile(r"^(?:(?P<sheet>'[ | 0 |
| `_CERT_RE` | `aeat\adapters\outbound\aeat\sede\_notifications.py:66` | adapters | _CERT_RE: Final[re.Pattern[str]] = re.compile(r"^\d{10, | 0 |
| `_CIF_PATTERN` | `aeat\core\identity\_documents.py:59` | core | _CIF_PATTERN = re.compile(rf"^([{_CIF_KIND_LETTERS}])(\ | 0 |
| `_CIF_RE` | `aeat\adapters\outbound\aeat\auth\certificate.py:568` | adapters | _CIF_RE = re.compile(r"^[ABCDEFGHJNPQRSUVW]0-9]{7}0-9 | 0 |
| `_CLI_KEY_PATTERN` | `aeat\application\wizard\_translations.py:101` | application | _CLI_KEY_PATTERN = re.compile(r"quote(cli\.\w+(?:\.\w+) | 0 |
| `_CLI_OBJECT_KEY_ASSIGNMENT_PATTERN` | `aeat\core\redaction\__init__.py:95` | core | _CLI_OBJECT_KEY_ASSIGNMENT_PATTERN = re.compile(     r" | 0 |
| `_CLI_OBJECT_KEY_TOKEN_PATTERN` | `aeat\core\redaction\__init__.py:100` | core | _CLI_OBJECT_KEY_TOKEN_PATTERN = re.compile(     r"(?i)\ | 0 |
| `_CLI_UUID_PATTERN` | `aeat\core\redaction\__init__.py:91` | core | _CLI_UUID_PATTERN = re.compile(     r"\b0-9a-fA-F]{8}- | 0 |
| `_COMBINING_MARK_RE` | `aeat\domain\calculations\registry\_text.py:10` | domain | _COMBINING_MARK_RE = re.compile(r"[\u0300-\u036f]+") | 0 |
| `_COMPACT_PDF_CRLF_ROW_RE` | `aeat\domain\calculations\registry\_record_design.py:512` | domain | _COMPACT_PDF_CRLF_ROW_RE = re.compile(     r"^\s*(?P<or | 0 |
| `_COMPACT_PDF_ROW_RE` | `aeat\domain\calculations\registry\_record_design.py:508` | domain | _COMPACT_PDF_ROW_RE = re.compile(     r"^\s*(?P<ordinal | 0 |
| `_COTEJO_CSV` | `aeat\adapters\outbound\aeat\sede\_parse.py:46` | adapters | _COTEJO_CSV: Final[re.Pattern[str]] = re.compile(     r | 0 |
| `_COUNTRY_CODE_RE` | `aeat\domain\calculations\registry\_schema.py:261` | domain | _COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$") | 0 |
| `_CP_RE` | `aeat\adapters\inbound\pdf\_scrub.py:62` | adapters | _CP_RE = re.compile(r"\b(?:CP\s*IC\.P\.\s*)0-9]{5}\b") | 0 |
| `_CSV_AUTHENTICITY_FOOTER_RE` | `aeat\adapters\inbound\justificante\_extract.py:54` | adapters | _CSV_AUTHENTICITY_FOOTER_RE = re.compile(     r"mediant | 0 |
| `_CSV_FALLBACK_RE` | `aeat\adapters\inbound\justificante\_extract.py:69` | adapters | _CSV_FALLBACK_RE = re.compile(r"\bCSV\s*[=:]\s*([A-Z0-9 | 0 |
| `_CSV_LABEL_EN_RE` | `aeat\adapters\inbound\justificante\_extract.py:62` | adapters | _CSV_LABEL_EN_RE = re.compile(     r"Secure\s+Verificat | 0 |
| `_CSV_LABEL_INVERTED_RE` | `aeat\adapters\inbound\justificante\_extract.py:44` | adapters | _CSV_LABEL_INVERTED_RE = re.compile(     r"\b([A-Z0-9]{ | 0 |
| `_CSV_LABEL_RE` | `aeat\adapters\inbound\justificante\_extract.py:37` | adapters | _CSV_LABEL_RE = re.compile(     r"C[óo]digo\s+Seguro\s+ | 0 |
| `_CSV_PATTERN` | `aeat\adapters\outbound\aeat\sede\_schema.py:42` | adapters | _CSV_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A | 0 |
| `_CSV_RE` | `aeat\adapters\inbound\borrador\_detect.py:19` | adapters | _CSV_RE = re.compile(r"C[óo]digo\s+Seguro\s+de\s+Verifi | 0 |
| `_CSV_RE` | `aeat\adapters\inbound\borrador\_extractors\modelo_100_summary_v2025.py:31` | adapters | _CSV_RE = re.compile(     r"C[óo]digo\s+Seguro\s+de\s+V | 0 |
| `_CSV_RE` | `aeat\adapters\inbound\pdf\_scrub.py:53` | adapters | _CSV_RE = re.compile(r"\b(?P<csv>[A-Z0-9]{16})\b") | 0 |
| `_CSV_SHAPE_RE` | `aeat\adapters\outbound\aeat\sede\_declarations.py:135` | adapters | _CSV_SHAPE_RE = re.compile(r"^[A-Z0-9]{8,24}$") | 0 |
| `_CSV_SYNTHETIC_RE` | `aeat\adapters\inbound\justificante\test_corpus_sidecar_roundtrip.py:56` | adapters | _CSV_SYNTHETIC_RE = re.compile(r"^SANITIZED(\d{3})(\d{4 | 0 |
| `_DATE_DDMMAAAA_RE` | `aeat\domain\calculations\registry\_schema.py:488` | domain | _DATE_DDMMAAAA_RE = re.compile(r"^(0[1-9]I[12]\dI3[01]) | 0 |
| `_DATE_DDMMYYYY_RE` | `aeat\core\parsing\_dates.py:31` | core | _DATE_DDMMYYYY_RE: Final = re.compile(r"^\s*(\d{2}[-/]\ | 0 |
| `_DATE_ISO_RE` | `aeat\domain\calculations\registry\_schema.py:489` | domain | _DATE_ISO_RE = re.compile(r"^\d{4}-(0[1-9]I1[0-2])-(0[1 | 0 |
| _(+152 more)_ | | | | |

### TypeAdapter instances
Count: 21

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `_ANY_HTTP_URL_ADAPTER` | `aeat\adapters\outbound\aeat\sede\_iva_compensation_wallet.py:47` | adapters | _ANY_HTTP_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAd | 0 |
| `_BIC` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:162` | domain | _BIC = TypeAdapter(BicString) | 0 |
| `_BINDING_ID_ADAPTER` | `aeat\entrypoints\cli\_modelo.py:96` | entrypoints | _BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(Bin | 0 |
| `_CASILLA_ID_ADAPTER` | `aeat\entrypoints\cli\_modelo.py:97` | entrypoints | _CASILLA_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(Cas | 0 |
| `_CCAA` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:98` | domain | _CCAA = TypeAdapter(CCAACode) | 0 |
| `_CHAPTERS_ADAPTER` | `aeat\domain\manuals\_loader.py:83` | domain | _CHAPTERS_ADAPTER: TypeAdapter[tuple[Chapter, ...]] = T | 0 |
| `_COUNTRY_ADAPTER` | `aeat\domain\calculations\registry\test_country_code_data_type.py:20` | domain | _COUNTRY_ADAPTER: TypeAdapter[str] = TypeAdapter(Countr | 0 |
| `_DATE` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:182` | domain | _DATE = TypeAdapter(CalendarDate) | 0 |
| `_HTTP_URL_ADAPTER` | `aeat\domain\categories\_proportionality.py:68` | domain | _HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl) | 0 |
| `_IBAN_ADAPTER` | `aeat\domain\calculations\registry\test_iban_data_type.py:19` | domain | _IBAN_ADAPTER: TypeAdapter[str] = TypeAdapter(IbanStrin | 0 |
| `_MUNI` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:146` | domain | _MUNI = TypeAdapter(MunicipalityCode) | 0 |
| `_NAME` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:57` | domain | _NAME = TypeAdapter(PersonOrEntityName) | 0 |
| `_NIFIVA` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:77` | domain | _NIFIVA = TypeAdapter(NifIvaString) | 0 |
| `_NIF_ADAPTER` | `aeat\domain\calculations\registry\test_nif_data_type.py:27` | domain | _NIF_ADAPTER: TypeAdapter[str] = TypeAdapter(NifString) | 0 |
| `_PERIOD_ADAPTER` | `aeat\domain\calculations\registry\test_period_code_data_type.py:24` | domain | _PERIOD_ADAPTER: TypeAdapter[str] = TypeAdapter(PeriodC | 0 |
| `_POSTAL` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:130` | domain | _POSTAL = TypeAdapter(PostalCode) | 0 |
| `_PROV` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:114` | domain | _PROV = TypeAdapter(ProvinceCode) | 0 |
| `_REVIEW_ITEM_ADAPTER` | `aeat\application\review\test_models.py:42` | application | _REVIEW_ITEM_ADAPTER: TypeAdapter[ReviewItem] = TypeAda | 0 |
| `_URL_ADAPTER` | `aeat\adapters\outbound\aeat\browser\_site_health.py:126` | adapters | _URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(Any | 5 |
| `_URL_ADAPTER` | `aeat\domain\portals\_entries\_common.py:22` | domain | _URL_ADAPTER: TypeAdapter[HttpUrl] = TypeAdapter(HttpUr | 5 |
| `_YEAR_ADAPTER` | `aeat\domain\calculations\registry\test_year_data_type.py:23` | domain | _YEAR_ADAPTER: TypeAdapter[int] = TypeAdapter(ModeloYea | 0 |

### Sentinel object() instances
Count: 0

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |

### SecureObjectNamespaceDefinition constants (UPPER_SNAKE_CASE)
Count: 37

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `AEAT_BROWSER_SESSION_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:448` | adapters | AEAT_BROWSER_SESSION_NAMESPACE = SecureObjectNamespaceD | 2 |
| `AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:520` | adapters | AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE = SecureObje | 2 |
| `AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:529` | adapters | AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE = SecureO | 2 |
| `AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:538` | adapters | AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE = SecureObjectNa | 2 |
| `APPLICATION_EVIDENCE_BUNDLE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:343` | adapters | APPLICATION_EVIDENCE_BUNDLE_NAMESPACE = SecureObjectNam | 4 |
| `APPLICATION_FILING_HISTORY_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:278` | adapters | APPLICATION_FILING_HISTORY_NAMESPACE = SecureObjectName | 2 |
| `ATTACHMENT_BLOB_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:430` | adapters | ATTACHMENT_BLOB_NAMESPACE = SecureObjectNamespaceDefini | 2 |
| `ATTACHMENT_MANIFEST_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:439` | adapters | ATTACHMENT_MANIFEST_NAMESPACE = SecureObjectNamespaceDe | 1 |
| `AUTH_APODERADO_CONFIGURATION_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:287` | adapters | AUTH_APODERADO_CONFIGURATION_NAMESPACE = SecureObjectNa | 2 |
| `CALCULATION_OBSERVATIONS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:296` | adapters | CALCULATION_OBSERVATIONS_NAMESPACE = SecureObjectNamesp | 2 |
| `CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:457` | adapters | CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE = SecureObjectNamespa | 3 |
| `GOOGLE_DRIVE_CONFIG_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:493` | adapters | GOOGLE_DRIVE_CONFIG_NAMESPACE = SecureObjectNamespaceDe | 2 |
| `GOOGLE_OAUTH_CLIENT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:466` | adapters | GOOGLE_OAUTH_CLIENT_NAMESPACE = SecureObjectNamespaceDe | 2 |
| `GOOGLE_OAUTH_METADATA_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:484` | adapters | GOOGLE_OAUTH_METADATA_NAMESPACE = SecureObjectNamespace | 2 |
| `GOOGLE_OAUTH_TOKEN_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:475` | adapters | GOOGLE_OAUTH_TOKEN_NAMESPACE = SecureObjectNamespaceDef | 2 |
| `IVA_COMPENSATION_HISTORY_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:323` | adapters | IVA_COMPENSATION_HISTORY_NAMESPACE = SecureObjectNamesp | 2 |
| `IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:305` | adapters | IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE = SecureO | 2 |
| `IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:314` | adapters | IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE = S | 2 |
| `LEDGER_CLASSIFICATION_RULES_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:352` | adapters | LEDGER_CLASSIFICATION_RULES_NAMESPACE = SecureObjectNam | 2 |
| `LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:361` | adapters | LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE = SecureObjectName | 1 |
| `LIVE_CENSUS_SNAPSHOT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:370` | adapters | LIVE_CENSUS_SNAPSHOT_NAMESPACE = SecureObjectNamespaceD | 3 |
| `LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:403` | adapters | LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE = SecureObjectNames | 4 |
| `LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:332` | adapters | LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE = SecureOb | 2 |
| `LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:412` | adapters | LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE = SecureObjectNam | 4 |
| `LIVE_VERIFY_OBSERVATION_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:421` | adapters | LIVE_VERIFY_OBSERVATION_NAMESPACE = SecureObjectNamespa | 4 |
| `LLM_CACHE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:502` | adapters | LLM_CACHE_NAMESPACE = SecureObjectNamespaceDefinition(  | 2 |
| `LLM_USAGE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:511` | adapters | LLM_USAGE_NAMESPACE = SecureObjectNamespaceDefinition(  | 3 |
| `PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:259` | adapters | PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE = SecureOb | 2 |
| `PROFILE_ASSETS_LEDGER_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:249` | adapters | PROFILE_ASSETS_LEDGER_NAMESPACE = SecureObjectNamespace | 2 |
| `PROFILE_INVENTORY_LEDGER_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:239` | adapters | PROFILE_INVENTORY_LEDGER_NAMESPACE = SecureObjectNamesp | 4 |
| `REPAIR_INTEGRITY_DECISION_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:269` | adapters | REPAIR_INTEGRITY_DECISION_NAMESPACE = SecureObjectNames | 2 |
| `TEST_SESSION_LIFECYCLE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:391` | adapters | TEST_SESSION_LIFECYCLE_NAMESPACE = SecureObjectNamespac | 2 |
| `TEST_SNAPSHOT_BASE_PROBE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:379` | adapters | TEST_SNAPSHOT_BASE_PROBE_NAMESPACE = SecureObjectNamesp | 2 |
| `USER_PROFILE_SNAPSHOT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:230` | adapters | USER_PROFILE_SNAPSHOT_NAMESPACE = SecureObjectNamespace | 4 |
| `USER_PROFILE_VALUE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:221` | adapters | USER_PROFILE_VALUE_NAMESPACE = SecureObjectNamespaceDef | 8 |
| `WORKFLOW_RUN_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:212` | adapters | WORKFLOW_RUN_NAMESPACE = SecureObjectNamespaceDefinitio | 1 |
| `WORKFLOW_STATE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:202` | adapters | WORKFLOW_STATE_NAMESPACE = SecureObjectNamespaceDefinit | 8 |

### AnyUrl / URL constants (UPPER_SNAKE_CASE)
Count: 5

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `AEAT_GROI_URL` | `aeat\domain\calculations\registry\_groi_oracle.py:64` | domain | AEAT_GROI_URL = AnyUrl(Settings.external_constants().ae | 5 |
| `AEAT_NIF_IVA_ENTRY_URL` | `aeat\domain\calculations\registry\_aeat_nif_iva_oracle.py:50` | domain | AEAT_NIF_IVA_ENTRY_URL = AnyUrl(f"{_EXTERNAL.aeat.domai | 3 |
| `AEAT_NIF_IVA_VERIFICATION_URL` | `aeat\domain\calculations\registry\_aeat_nif_iva_oracle.py:44` | domain | AEAT_NIF_IVA_VERIFICATION_URL = AnyUrl(_EXTERNAL.aeat.o | 3 |
| `RENTA_WEB_OPEN_APP_URL` | `aeat\domain\calculations\registry\_renta_web_open_oracle.py:25` | domain | RENTA_WEB_OPEN_APP_URL = AnyUrl(_EXTERNAL.aeat.oracles. | 3 |
| `RENTA_WEB_OPEN_LANDING_URL` | `aeat\domain\calculations\registry\_renta_web_open_oracle.py:24` | domain | RENTA_WEB_OPEN_LANDING_URL = AnyUrl(f"{_EXTERNAL.aeat.d | 2 |

### Decimal / numeric threshold constants
Count: 6

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `ART_23_1_F_RATE` | `aeat\domain\fincas\_amortization_ledger.py:30` | domain | ART_23_1_F_RATE: Decimal = Decimal("0.03") | 1 |
| `DAYS_PER_YEAR` | `aeat\domain\fincas\_amortization_ledger.py:33` | domain | DAYS_PER_YEAR: Decimal = Decimal("365") | 0 |
| `M347_THRESHOLD_EUR` | `aeat\domain\modelos\_row_models.py:276` | domain | M347_THRESHOLD_EUR: Decimal = Decimal("3005.06") | 3 |
| `PRIOR_RENT_REBAJA_THRESHOLD` | `aeat\domain\fincas\_tier_resolver.py:61` | domain | PRIOR_RENT_REBAJA_THRESHOLD: Decimal = Decimal("0.05") | 1 |
| `THRESHOLD_347_EUR` | `aeat\application\aggregation\_counterpart.py:311` | application | THRESHOLD_347_EUR: Decimal = Decimal("3005.06") | 1 |
| `THRESHOLD_720_EUR_PER_CLASS` | `aeat\application\aggregation\_foreign_assets.py:153` | application | THRESHOLD_720_EUR_PER_CLASS: Decimal = Decimal("50000.0 | 1 |

### String constants (UPPER_SNAKE_CASE)
Count: 71 — showing all

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `ALL_TOKEN` | `aeat\domain\auth\apoderamientos\_catalogue.py:15` | domain | ALL_TOKEN = "ALL" | 2 |
| `APPROVAL_BASIS_VERSION` | `aeat\domain\filing\_schema.py:25` | domain | APPROVAL_BASIS_VERSION = "review-basis-v1" | 2 |
| `ASSETS_AMORTIZATION_LEDGER_FILENAME` | `aeat\adapters\persistence\profile\assets.py:27` | adapters | ASSETS_AMORTIZATION_LEDGER_FILENAME = "assets-amortizat | 0 |
| `ASSETS_LEDGER_FILENAME` | `aeat\adapters\persistence\profile\assets.py:26` | adapters | ASSETS_LEDGER_FILENAME = "assets-ledger.secure-object" | 0 |
| `BINARY_MIME_TYPE` | `aeat\core\external_constants.py:27` | core | BINARY_MIME_TYPE: Final[str] = "application/octet-strea | 2 |
| `BUCKETS_DIRNAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:19` | adapters | BUCKETS_DIRNAME = "buckets" | 8 |
| `BUCKET_AUDIT_DIRNAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:22` | adapters | BUCKET_AUDIT_DIRNAME = "audit" | 2 |
| `BUCKET_BLOBS_DIRNAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:21` | adapters | BUCKET_BLOBS_DIRNAME = "blobs" | 2 |
| `BUCKET_DB_DIRNAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:20` | adapters | BUCKET_DB_DIRNAME = "db" | 5 |
| `BUCKET_DEK_FILENAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:26` | adapters | BUCKET_DEK_FILENAME = "bucket.dek.json" | 3 |
| `BUCKET_LOCK_FILENAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:24` | adapters | BUCKET_LOCK_FILENAME = ".lock" | 3 |
| `BUCKET_MANIFEST_FILENAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:23` | adapters | BUCKET_MANIFEST_FILENAME = "manifest.toml" | 3 |
| `CENSUS_MODELO_SERVICE_OWNER` | `aeat\domain\calculations\registry\_censo_modelos.py:17` | domain | CENSUS_MODELO_SERVICE_OWNER = "aeat.domain.calculations | 2 |
| `CENSUS_SOURCE_TAG` | `aeat\application\user_profile\_censo_sync.py:52` | application | CENSUS_SOURCE_TAG: Final = "aeat_census_read" | 2 |
| `CERTIFICATE_CONTEXT_MARKER` | `aeat\adapters\outbound\aeat\auth\_certificate_backends\_base.py:18` | adapters | CERTIFICATE_CONTEXT_MARKER = "_aeat_certificate_thumbpr | 7 |
| `CLASSIFIED_BY_MANUAL` | `aeat\core\external_constants.py:38` | core | CLASSIFIED_BY_MANUAL: Final[str] = "manual" | 7 |
| `CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE` | `aeat\adapters\outbound\aeat\auth\_clave_movil.py:83` | adapters | CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE: Final[str] = "aeat.ou | 4 |
| `CLI_BUCKET_ID_PLACEHOLDER` | `aeat\core\redaction\__init__.py:88` | core | CLI_BUCKET_ID_PLACEHOLDER = "<bucket-id>" | 3 |
| `CLI_OBJECT_KEY_PLACEHOLDER` | `aeat\core\redaction\__init__.py:89` | core | CLI_OBJECT_KEY_PLACEHOLDER = "<object-key>" | 3 |
| `CLI_PROFILE_ID_PLACEHOLDER` | `aeat\core\redaction\__init__.py:87` | core | CLI_PROFILE_ID_PLACEHOLDER = "<profile-id>" | 4 |
| `CSV_MIME_TYPE` | `aeat\core\external_constants.py:33` | core | CSV_MIME_TYPE: Final[str] = "text/csv" | 1 |
| `DEFAULT_CURRENCY` | `aeat\core\external_constants.py:24` | core | DEFAULT_CURRENCY: Final[str] = "EUR" | 16 |
| `DEFAULT_OUTPUT_LANGUAGE` | `aeat\core\i18n\_render.py:28` | core | DEFAULT_OUTPUT_LANGUAGE: Final[str] = "es" | 2 |
| `DEV_TEST_DATABASE_PASSWORD` | `aeat\core\config.py:61` | core | DEV_TEST_DATABASE_PASSWORD = "aeat-dev-test-database-pa | 0 |
| `DEV_TEST_DATABASE_PASSWORD_ENV_VAR` | `aeat\core\config.py:63` | core | DEV_TEST_DATABASE_PASSWORD_ENV_VAR = "AEAT_DEV_TEST_DAT | 0 |
| `GROI_ORACLE_ID` | `aeat\domain\calculations\registry\_groi_oracle.py:60` | domain | GROI_ORACLE_ID = "aeat-groi-spanish-roi-checker" | 6 |
| `HEADER_FONT` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:34` | tests | HEADER_FONT = "Helvetica-Bold" | 0 |
| `INVENTORY_LEDGER_FILENAME` | `aeat\adapters\persistence\profile\inventory.py:26` | adapters | INVENTORY_LEDGER_FILENAME = "inventory-ledger.secure-ob | 0 |
| `JSON_MIME_TYPE` | `aeat\core\external_constants.py:30` | core | JSON_MIME_TYPE: Final[str] = "application/json" | 1 |
| `KEYRING_SERVICE` | `aeat\adapters\persistence\storage\master_key\_master_key.py:120` | adapters | KEYRING_SERVICE: Final[str] = "aeat:secure-persistence" | 0 |
| `KEYRING_USERNAME` | `aeat\adapters\persistence\storage\master_key\_master_key.py:123` | adapters | KEYRING_USERNAME: Final[str] = "master" | 1 |
| `KEYSTORE_DIRNAME` | `aeat\adapters\persistence\storage\_namespace_registry.py:25` | adapters | KEYSTORE_DIRNAME = "keystore" | 2 |
| `LABEL_FONT` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:36` | tests | LABEL_FONT = "Helvetica" | 1 |
| `LATIN_1_ENCODING` | `aeat\core\external_constants.py:301` | core | LATIN_1_ENCODING: Final[str] = "latin-1" | 0 |
| `LEDGER_RENTA_EXPENSE_SOURCE` | `aeat\domain\renta\_ledger_expenses.py:28` | domain | LEDGER_RENTA_EXPENSE_SOURCE = "ledger_renta_expense_agg | 2 |
| `LIVE_OPT_IN_ENV` | `aeat\tests\conftest.py:57` | tests | LIVE_OPT_IN_ENV: str = "AEAT_LIVE_TESTS_ENABLED" | 0 |
| `ORACLE_ID` | `aeat\domain\calculations\registry\_aeat_nif_iva_oracle.py:41` | domain | ORACLE_ID = "aeat-nif-iva-checker" | 5 |
| `OUTPUT_LANGUAGE_ENV_VAR` | `aeat\core\i18n\_render.py:27` | core | OUTPUT_LANGUAGE_ENV_VAR: Final[str] = "AEAT_OUTPUT_LANG | 3 |
| `OUTSIDE_PERIOD` | `aeat\application\aggregation\_shared_issue_reasons.py:31` | application | OUTSIDE_PERIOD: Final[str] = "outside_period" | 0 |
| `PASSPHRASE_ENV_VAR` | `aeat\adapters\persistence\storage\master_key\_master_key.py:126` | adapters | PASSPHRASE_ENV_VAR: Final[str] = "AEAT_SECRET_PASSPHRAS | 0 |
| `PDF_EXTENSION` | `aeat\core\external_constants.py:289` | core | PDF_EXTENSION: Final[str] = ".pdf" | 5 |
| `PDF_MIME_TYPE` | `aeat\core\external_constants.py:286` | core | PDF_MIME_TYPE: Final[str] = "application/pdf" | 0 |
| `PERSONAL_TRANSACTION` | `aeat\application\aggregation\_shared_issue_reasons.py:30` | application | PERSONAL_TRANSACTION: Final[str] = "personal_transactio | 0 |
| `PLAYWRIGHT_WAIT_DOMCONTENTLOADED` | `aeat\adapters\outbound\aeat\sede\_browser_constants.py:15` | adapters | PLAYWRIGHT_WAIT_DOMCONTENTLOADED: Final[str] = "domcont | 2 |
| `PLAYWRIGHT_WAIT_NETWORKIDLE` | `aeat\adapters\outbound\aeat\sede\_browser_constants.py:19` | adapters | PLAYWRIGHT_WAIT_NETWORKIDLE: Final[str] = "networkidle" | 2 |
| `PROVENANCE_SOURCE_MANUAL_CLI` | `aeat\core\external_constants.py:306` | core | PROVENANCE_SOURCE_MANUAL_CLI: Final[str] = "manual_cli" | 0 |
| `REMOTE_MIRROR_MANIFEST_NAMESPACE` | `aeat\adapters\outbound\storage\_mirror_manifest.py:20` | adapters | REMOTE_MIRROR_MANIFEST_NAMESPACE = "_sync-state" | 3 |
| `RENTA_WEB_OPEN_ORACLE_ID` | `aeat\domain\calculations\registry\test_live_parity_audit.py:48` | domain | RENTA_WEB_OPEN_ORACLE_ID = "modelo-100-renta-web-open" | 0 |
| `REPLAY_ACTIVE_ENV_VAR` | `aeat\core\observability\_replay.py:26` | core | REPLAY_ACTIVE_ENV_VAR = "AEAT_REPLAY_ACTIVE" | 2 |
| `SANITIZER_VERSION` | `aeat\adapters\inbound\sanitizer\_pipeline.py:63` | adapters | SANITIZER_VERSION = "0.1.0" | 1 |
| `SCHEMA_VERSION` | `aeat\domain\profile\assets\__init__.py:20` | domain | SCHEMA_VERSION = "1" | 0 |
| `SCHEMA_VERSION` | `aeat\domain\profile\inventory\__init__.py:34` | domain | SCHEMA_VERSION = "1" | 0 |
| `SCRUB_VERSION` | `aeat\adapters\inbound\pdf\_scrub.py:47` | adapters | SCRUB_VERSION = "1.0.0" | 1 |
| `SECRET_PASSPHRASE` | `aeat\adapters\outbound\aeat\auth\test_authenticator.py:60` | adapters | SECRET_PASSPHRASE = "correct-horse-battery-staple" | 0 |
| `SECRET_PASSPHRASE` | `aeat\adapters\outbound\aeat\auth\test_certificate.py:41` | adapters | SECRET_PASSPHRASE = "correct-horse-battery-staple" | 0 |
| `SECURE_OBJECT_CATALOGUE_KEY` | `aeat\adapters\persistence\storage\_namespace_registry.py:15` | adapters | SECURE_OBJECT_CATALOGUE_KEY = "catalogue" | 2 |
| `SECURE_OBJECT_DEFAULT_KEY` | `aeat\adapters\persistence\storage\_namespace_registry.py:16` | adapters | SECURE_OBJECT_DEFAULT_KEY = "default" | 2 |
| `SECURE_OBJECT_WORKFLOW_STATE_KEY` | `aeat\adapters\persistence\storage\_namespace_registry.py:17` | adapters | SECURE_OBJECT_WORKFLOW_STATE_KEY = "state" | 2 |
| `SEDE_BODY_ENCODING` | `aeat\adapters\outbound\aeat\sede\_browser_constants.py:28` | adapters | SEDE_BODY_ENCODING: Final[str] = "latin-1" | 0 |
| `SPANISH_AMOUNT_GROUP` | `aeat\adapters\inbound\pdf\_label_regex.py:35` | adapters | SPANISH_AMOUNT_GROUP = r"(-?0-9]{1,3}(?:[.  ]0-9]{3}) | 4 |
| `SYSTEM_BUCKET_ID` | `aeat\application\workflow\_events.py:27` | application | SYSTEM_BUCKET_ID: Final[str] = "system" | 0 |
| `TEXT_VALUE_GROUP` | `aeat\adapters\inbound\pdf\_label_regex.py:52` | adapters | TEXT_VALUE_GROUP = r"(\S+?)\s*$" | 1 |
| `TX_BUCKET_NAMESPACE` | `aeat\domain\transactions\_repository.py:28` | domain | TX_BUCKET_NAMESPACE = "aeat.domain.transactions.bucket" | 4 |
| `UNCLASSIFIED_BUSINESS_STATE` | `aeat\application\aggregation\_shared_issue_reasons.py:29` | application | UNCLASSIFIED_BUSINESS_STATE: Final[str] = "unclassified | 0 |
| `UNSUPPORTED_CURRENCY` | `aeat\application\aggregation\_shared_issue_reasons.py:28` | application | UNSUPPORTED_CURRENCY: Final[str] = "unsupported_currenc | 0 |
| `UNSUPPORTED_DIRECTION` | `aeat\application\aggregation\_shared_issue_reasons.py:27` | application | UNSUPPORTED_DIRECTION: Final[str] = "unsupported_direct | 0 |
| `VALUE_FONT` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:38` | tests | VALUE_FONT = "Helvetica" | 0 |
| `WORKFLOW_STATE_OBJECT_ID` | `aeat\application\workflow\_events.py:28` | application | WORKFLOW_STATE_OBJECT_ID: Final[str] = "aeat.workflow:s | 0 |
| `XLSM_EXTENSION` | `aeat\core\external_constants.py:298` | core | XLSM_EXTENSION: Final[Literal[".xlsm"]] = ".xlsm" | 0 |
| `XLSX_EXTENSION` | `aeat\core\external_constants.py:295` | core | XLSX_EXTENSION: Final[Literal[".xlsx"]] = ".xlsx" | 4 |
| `XLS_EXTENSION` | `aeat\core\external_constants.py:292` | core | XLS_EXTENSION: Final[Literal[".xls"]] = ".xls" | 0 |

### Integer constants (UPPER_SNAKE_CASE)
Count: 23

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION` | `aeat\adapters\outbound\aeat\auth\_clave_movil.py:80` | adapters | AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION: Final[int] =  | 0 |
| `AEAT_STORAGE_STATE_SCHEMA_VERSION` | `aeat\adapters\outbound\aeat\auth\_authenticator.py:98` | adapters | AEAT_STORAGE_STATE_SCHEMA_VERSION: Final[int] = 1 | 0 |
| `BLOB_MANIFEST_SCHEMA_VERSION` | `aeat\adapters\persistence\storage\_namespace_registry.py:27` | adapters | BLOB_MANIFEST_SCHEMA_VERSION = 1 | 3 |
| `CARRY_FORWARD_MAX_YEARS` | `aeat\domain\fincas\_expense_rollup.py:29` | domain | CARRY_FORWARD_MAX_YEARS: int = 4 | 1 |
| `DEFAULT_EJERCICIO_AMENDMENT_YEAR` | `aeat\domain\fincas\_tier_resolver.py:51` | domain | DEFAULT_EJERCICIO_AMENDMENT_YEAR: int = 2024 | 2 |
| `FILING_YEAR` | `aeat\domain\profile\test_custodia_compartida.py:30` | domain | FILING_YEAR = 2024 | 0 |
| `FILING_YEAR` | `aeat\domain\profile\test_descendant_info.py:35` | domain | FILING_YEAR = 2024 | 0 |
| `FILING_YEAR` | `aeat\domain\profile\test_marriage_facts.py:30` | domain | FILING_YEAR = 2024 | 0 |
| `GCM_TAG_SIZE` | `aeat\adapters\persistence\storage\crypto\_crypto.py:35` | adapters | GCM_TAG_SIZE: int = 16 | 3 |
| `HEADER_FONT_SIZE` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:35` | tests | HEADER_FONT_SIZE = 12 | 0 |
| `JOVEN_TENANT_AGE_MAX` | `aeat\domain\fincas\_tier_resolver.py:67` | domain | JOVEN_TENANT_AGE_MAX: int = 35 | 1 |
| `JOVEN_TENANT_AGE_MIN` | `aeat\domain\fincas\_tier_resolver.py:66` | domain | JOVEN_TENANT_AGE_MIN: int = 18 | 1 |
| `KEY_SIZE` | `aeat\adapters\persistence\storage\crypto\_crypto.py:38` | adapters | KEY_SIZE: int = 32 | 11 |
| `LABEL_FONT_SIZE` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:37` | tests | LABEL_FONT_SIZE = 9 | 1 |
| `MINIMUM_DISPLAY_ID_WIDTH` | `aeat\application\ledger\_id_resolution.py:26` | application | MINIMUM_DISPLAY_ID_WIDTH = 8 | 2 |
| `NIST_PASSPHRASE_MIN_LENGTH` | `aeat\adapters\persistence\storage\master_key\_master_key.py:84` | adapters | NIST_PASSPHRASE_MIN_LENGTH: Final[int] = 8 | 0 |
| `NONCE_SIZE` | `aeat\adapters\persistence\storage\crypto\_crypto.py:32` | adapters | NONCE_SIZE: int = 12 | 3 |
| `PLAYWRIGHT_TIMEOUT_SHORT_MS` | `aeat\adapters\outbound\aeat\sede\_browser_constants.py:23` | adapters | PLAYWRIGHT_TIMEOUT_SHORT_MS: Final[int] = 2_000 | 0 |
| `REHAB_LOOKBACK_DAYS` | `aeat\domain\fincas\_tier_resolver.py:55` | domain | REHAB_LOOKBACK_DAYS: int = 730 | 1 |
| `REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION` | `aeat\adapters\outbound\storage\_mirror_manifest.py:21` | adapters | REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION = 1 | 1 |
| `SECRET_RECORD_SCHEMA_VERSION` | `aeat\adapters\persistence\storage\_namespace_registry.py:28` | adapters | SECRET_RECORD_SCHEMA_VERSION = 1 | 2 |
| `SECURE_OBJECT_SCHEMA_VERSION_V1` | `aeat\adapters\persistence\storage\_namespace_registry.py:14` | adapters | SECURE_OBJECT_SCHEMA_VERSION_V1 = 1 | 1 |
| `VALUE_FONT_SIZE` | `aeat\tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generator_shared.py:39` | tests | VALUE_FONT_SIZE = 10 | 0 |

### Tuple / frozenset / set literal constants (UPPER_SNAKE_CASE)
Count: 57

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `ACCEPTED_ROOTS` | `aeat\application\operator_surface\_contract.py:29` | application | ACCEPTED_ROOTS: tuple[RootSurface, ...] = (     RootSur | 1 |
| `ACCEPTED_SOURCE_KINDS` | `aeat\application\aggregation\_service.py:49` | application | ACCEPTED_SOURCE_KINDS: tuple[AggregationSourceKind, ... | 3 |
| `AEAT_WRITE_FORBIDDEN_ACTIONS` | `aeat\domain\calculations\registry\_remote_state_guard.py:36` | domain | AEAT_WRITE_FORBIDDEN_ACTIONS: tuple[str, ...] = (     " | 6 |
| `AEAT_WRITE_FORBIDDEN_VERB_TOKENS` | `aeat\domain\calculations\registry\_remote_state_guard.py:70` | domain | AEAT_WRITE_FORBIDDEN_VERB_TOKENS: frozenset[str] = froz | 4 |
| `ALLOWED_CLICK_OVERRIDES` | `aeat\adapters\outbound\aeat\sede\_renta_web_open_safety.py:103` | adapters | ALLOWED_CLICK_OVERRIDES: frozenset[str] = frozenset() | 1 |
| `AUTH_DIAGNOSTIC_PHONE_STATES` | `aeat\application\auth\_diagnostics.py:22` | application | AUTH_DIAGNOSTIC_PHONE_STATES: tuple[str, ...] = (     " | 2 |
| `AUTH_PROVIDER_CATALOGUE` | `aeat\application\auth\_catalogue.py:36` | application | AUTH_PROVIDER_CATALOGUE: tuple[AuthProviderListing, ... | 2 |
| `BANNED_LIVE_IMPORTS` | `aeat\tests\conftest.py:40` | tests | BANNED_LIVE_IMPORTS: frozenset[str] = frozenset(     {  | 0 |
| `BOOTSTRAP_EXEMPT_VERB_PATHS` | `aeat\entrypoints\cli\_bootstrap_exempt.py:35` | entrypoints | BOOTSTRAP_EXEMPT_VERB_PATHS: tuple[str, ...] = (     #  | 0 |
| `BULK_CLASSIFY_ALLOWED_COLUMNS` | `aeat\application\ledger\_models.py:720` | application | BULK_CLASSIFY_ALLOWED_COLUMNS: frozenset[str] = frozens | 2 |
| `CANONICAL_CRUD_VERBS` | `aeat\application\operator_surface\_crud_contract.py:37` | application | CANONICAL_CRUD_VERBS: frozenset[CrudVerb] = frozenset(C | 3 |
| `CANONICAL_LAYOUT_PACKAGES` | `aeat\tests\test_layout_import_smoke.py:23` | tests | CANONICAL_LAYOUT_PACKAGES: tuple[str, ...] = (     "aea | 0 |
| `CANONICAL_PUBLIC_SYMBOLS` | `aeat\tests\test_layout_import_smoke.py:89` | tests | CANONICAL_PUBLIC_SYMBOLS: tuple[tuple[str, str], ...] = | 0 |
| `CAPPED_CATEGORIES` | `aeat\domain\fincas\_expense_rollup.py:32` | domain | CAPPED_CATEGORIES: frozenset[ExpenseCategory] = frozens | 1 |
| `CENSUS_DERIVED_FIELDS` | `aeat\domain\user_profile\test_census_schema_fields.py:16` | domain | CENSUS_DERIVED_FIELDS: tuple[tuple[str, str], ...] = (  | 0 |
| `CENSUS_MODELO_ERROR_CODES` | `aeat\domain\calculations\registry\_censo_modelos.py:19` | domain | CENSUS_MODELO_ERROR_CODES: tuple[str, ...] = ("ERROR_CA | 2 |
| `CENSUS_MODELO_EVENT_KINDS` | `aeat\domain\calculations\registry\_censo_modelos.py:18` | domain | CENSUS_MODELO_EVENT_KINDS: tuple[str, ...] = ("alta", " | 2 |
| `CLASSIFIED_STATES` | `aeat\domain\transactions\_enums.py:107` | domain | CLASSIFIED_STATES: frozenset[BusinessClassification] =  | 1 |
| `COUNTERPART_BINDING_SOURCE_KINDS` | `aeat\domain\calculations\registry\_bindings.py:1636` | domain | COUNTERPART_BINDING_SOURCE_KINDS: frozenset[Counterpart | 0 |
| `COVERAGE_GAPS` | `aeat\test_coverage_inventory.py:58` | test_coverage_inventory.py | COVERAGE_GAPS: frozenset[str] = frozenset(     {        | 0 |
| `CSV_ENCODING_FALLBACK_CHAIN` | `aeat\core\external_constants.py:303` | core | CSV_ENCODING_FALLBACK_CHAIN: tuple[str, ...] = ("utf-8- | 2 |
| `CSV_EXTENSIONS` | `aeat\adapters\inbound\financial\providers\_constants.py:21` | adapters | CSV_EXTENSIONS: frozenset[str] = frozenset({".csv", ".t | 3 |
| `CSV_LAYOUTS` | `aeat\adapters\inbound\financial\providers\_csv.py:158` | adapters | CSV_LAYOUTS: tuple[CsvBankLayout, ...] = (     N26_LAYO | 1 |
| `DECIMAL_STR_PENDING` | `aeat\test_decimal_enrollment_inventory.py:55` | test_decimal_enrollment_inventory.py | DECIMAL_STR_PENDING: frozenset[str] = frozenset(     {  | 0 |
| `DOMAIN_NAMESPACE_DEFINITIONS` | `aeat\adapters\persistence\storage\_namespace_registry.py:548` | adapters | DOMAIN_NAMESPACE_DEFINITIONS = (     SecureObjectNamesp | 1 |
| `ERROR_CODES` | `aeat\application\aggregation\_service.py:56` | application | ERROR_CODES: tuple[str, ...] = (     "ERROR_FINANCIAL_A | 2 |
| `ERROR_CODES` | `aeat\application\operator_surface\_contract.py:332` | application | ERROR_CODES: tuple[str, ...] = ("REFUSED_OPERATOR_SURFA | 2 |
| `EU_MEMBER_STATE_CODES` | `aeat\domain\invoices\_validators.py:36` | domain | EU_MEMBER_STATE_CODES: frozenset[str] = frozenset(membe | 1 |
| `EXPECTED_LEDGER_VERBS` | `aeat\entrypoints\cli\test_ledger_verb_spine.py:24` | entrypoints | EXPECTED_LEDGER_VERBS: frozenset[str] = frozenset(      | 0 |
| `EXPECTED_OVERVIEW_VERBS` | `aeat\entrypoints\cli\test_overview_explain_verb.py:22` | entrypoints | EXPECTED_OVERVIEW_VERBS: frozenset[str] = frozenset(    | 0 |
| `FORBIDDEN_URL_FRAGMENTS` | `aeat\adapters\outbound\aeat\sede\_renta_web_open_safety.py:86` | adapters | FORBIDDEN_URL_FRAGMENTS: frozenset[str] = frozenset(    | 1 |
| `INVOICE_BINDING_SOURCE_KINDS` | `aeat\domain\calculations\registry\_bindings.py:32` | domain | INVOICE_BINDING_SOURCE_KINDS: frozenset[str] = frozense | 0 |
| `KNOWN_VERIFICATION_PREDICATE_OPERATORS` | `aeat\domain\calculations\registry\_schema.py:2382` | domain | KNOWN_VERIFICATION_PREDICATE_OPERATORS: frozenset[str]  | 3 |
| `LINK_CHECK_PREFLIGHT` | `aeat\entrypoints\cli\test_ledger_verb_spine.py:52` | entrypoints | LINK_CHECK_PREFLIGHT: frozenset[str] = frozenset({"link | 0 |
| `LIVE_ACCESS_MARKERS` | `aeat\tests\conftest.py:37` | tests | LIVE_ACCESS_MARKERS: frozenset[str] = frozenset({"live_ | 0 |
| `MIGRATED_COMMANDS` | `aeat\entrypoints\cli\test_json_schema_conformance.py:53` | entrypoints | MIGRATED_COMMANDS: frozenset[str] = frozenset(     {    | 0 |
| `MODELOS_WITHOUT_SHIFT` | `aeat\domain\deadlines\_festivos.py:187` | domain | MODELOS_WITHOUT_SHIFT: tuple[str, ...] = ("369",) | 2 |
| `MOUNTED_COMMAND_FAMILIES` | `aeat\application\operator_surface\_contract.py:174` | application | MOUNTED_COMMAND_FAMILIES: tuple[MountedCommandFamily, . | 1 |
| `PART_SPECS` | `aeat\domain\manuals\_fetch.py:61` | domain | PART_SPECS: tuple[PartSpec, ...] = (     PartSpec(      | 2 |
| `PENDING_ENROLLMENT` | `aeat\test_clock_enrollment_inventory.py:79` | test_clock_enrollment_inventory.py | PENDING_ENROLLMENT: frozenset[str] = frozenset(     {   | 0 |
| `PIPELINE_ONLY_CLASSIFICATIONS` | `aeat\domain\transactions\_llm.py:138` | domain | PIPELINE_ONLY_CLASSIFICATIONS: frozenset[BusinessClassi | 1 |
| `PROFILE_BOUND_WRITE_VERB_PATHS` | `aeat\application\storage_write_policy.py:49` | application | PROFILE_BOUND_WRITE_VERB_PATHS: tuple[str, ...] = (     | 0 |
| `REQUIRED_RELOCATED_PATHS` | `aeat\tests\test_layout_import_smoke.py:101` | tests | REQUIRED_RELOCATED_PATHS: tuple[str, ...] = (     "appl | 0 |
| `REQUIRED_SCOPES` | `aeat\adapters\outbound\google\_records.py:36` | adapters | REQUIRED_SCOPES: tuple[str, ...] = (OPENID_SCOPE, EMAIL | 9 |
| `RETIRED_OPERATOR_SURFACES` | `aeat\application\operator_surface\_contract.py:46` | application | RETIRED_OPERATOR_SURFACES: tuple[RetiredOperatorSurface | 1 |
| `RUNTIME_SURFACES` | `aeat\entrypoints\cli\test_retired_cli_literals.py:10` | entrypoints | RUNTIME_SURFACES = (     PROJECT_ROOT / "src" / "aeat", | 0 |
| `SANITIZED_SHAS` | `aeat\adapters\inbound\sanitizer\fixtures.py:23` | adapters | SANITIZED_SHAS: frozenset[str] = frozenset(     {       | 0 |
| `SCRUB_FIELD_PATTERNS` | `aeat\core\logging.py:36` | core | SCRUB_FIELD_PATTERNS: tuple[str, ...] = (     "access_t | 0 |
| `SERVICE_OWNERS` | `aeat\application\operator_surface\_contract.py:296` | application | SERVICE_OWNERS: tuple[ServiceOwner, ...] = (     Servic | 0 |
| `SOURCE_KINDS` | `aeat\application\operator_surface\_contract.py:160` | application | SOURCE_KINDS: tuple[SourceKind, ...] = (     SourceKind | 0 |
| `SOURCE_KIND_ALIASES` | `aeat\application\operator_surface\_contract.py:167` | application | SOURCE_KIND_ALIASES: tuple[SourceKindAlias, ...] = (    | 1 |
| `STORAGE_PATH_DEFINITIONS` | `aeat\adapters\persistence\storage\_namespace_registry.py:665` | adapters | STORAGE_PATH_DEFINITIONS = (     StoragePathDefinition( | 1 |
| `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` | `aeat\application\user_profile\_bundle.py:33` | application | SUPPORTED_BUNDLE_SCHEMA_VERSIONS: frozenset[int] = froz | 1 |
| `SUPPORTED_OUTPUT_LANGUAGES` | `aeat\core\i18n\_render.py:29` | core | SUPPORTED_OUTPUT_LANGUAGES: tuple[str, ...] = ("es", "e | 12 |
| `TEXT_SUFFIXES` | `aeat\entrypoints\cli\test_retired_cli_literals.py:14` | entrypoints | TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".example"} | 0 |
| `UE_EEA_COUNTRY_CODES` | `aeat\domain\profile\_renta_codes.py:50` | domain | UE_EEA_COUNTRY_CODES: frozenset[str] = frozenset({      | 1 |
| `WIZARD_FLOWS` | `aeat\application\wizard\_catalogue.py:857` | application | WIZARD_FLOWS: tuple[WizardFlow, ...] = (SETUP_FLOW,) | 5 |

### Dict literal constants (UPPER_SNAKE_CASE)
Count: 4

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `CATEGORY_FAMILY_MEMBERS` | `aeat\domain\categories\_spending_category.py:101` | domain | CATEGORY_FAMILY_MEMBERS: dict[SpendingCategoryFamily, t | 3 |
| `ENCODING_ALIAS_MAP` | `aeat\domain\calculations\registry\_record_spec.py:15` | domain | ENCODING_ALIAS_MAP: Mapping[str, str] = {     "latin-1" | 2 |
| `FIRST_SLICE_EXPENSE_CASILLAS` | `aeat\domain\renta\_first_slice_routing.py:26` | domain | FIRST_SLICE_EXPENSE_CASILLAS: Mapping[SpendingCategory, | 2 |
| `SCHEMA_REGISTRY` | `aeat\core\json_contract.py:102` | core | SCHEMA_REGISTRY: dict[str, RegisteredSchema] = {} | 2 |

### re.compile constants (all casing)
Count: 202

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `_A1_COLUMN` | `aeat\application\storage\calc_sheets\_records.py:76` | application | _A1_COLUMN = re.compile(r"^[A-Z]{1,3}$") | 0 |
| `_AEAT_KEY_PATTERN` | `aeat\core\test_settings_single_surface_invariant.py:52` | core | _AEAT_KEY_PATTERN: re.Pattern[str] = re.compile(r"^AEAT | 0 |
| `_AMOUNT_RE` | `aeat\adapters\inbound\pdf\_scrub.py:52` | adapters | _AMOUNT_RE = re.compile(r"\b(?P<whole>0-9]{1,3}(?:\.[0 | 0 |
| `_ANNUAL_PERIOD_RE` | `aeat\domain\period.py:52` | domain | _ANNUAL_PERIOD_RE = re.compile(r"^(?P<year>\d{4})A$") | 0 |
| `_ANNUAL_RE` | `aeat\application\filing\_import.py:39` | application | _ANNUAL_RE = re.compile(r"^0A$") | 0 |
| `_ANNUAL_RE` | `aeat\application\filing\reconciliation\_reconcile.py:68` | application | _ANNUAL_RE: Final[re.Pattern[str]] = re.compile(r"^(?P< | 0 |
| `_ANNUAL_TOKEN_RE` | `aeat\application\filing\_testing_registry.py:109` | application | _ANNUAL_TOKEN_RE = re.compile(r"^0A$") | 0 |
| `_BARE_NUMERIC_RE` | `aeat\entrypoints\cli\_modelo.py:94` | entrypoints | _BARE_NUMERIC_RE = re.compile(r"^\d+$") | 0 |
| `_BARE_PERIOD_RE` | `aeat\domain\calculations\registry\_queries.py:32` | domain | _BARE_PERIOD_RE = re.compile(     r"^(?:0AI[1-4]TI[1-4] | 0 |
| `_BARE_YEAR_RE` | `aeat\domain\period.py:53` | domain | _BARE_YEAR_RE = re.compile(r"^\d{4}$") | 0 |
| `_BEARER_TOKEN_RE` | `aeat\core\logging.py:71` | core | _BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0 | 0 |
| `_BIC_RE` | `aeat\domain\calculations\registry\_schema.py:470` | domain | _BIC_RE = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3} | 0 |
| `_BORRADOR_RE` | `aeat\adapters\inbound\borrador\_detect.py:18` | adapters | _BORRADOR_RE = re.compile(r"\bBORRADOR\b", re.IGNORECAS | 0 |
| `_CADASTRAL_RE` | `aeat\adapters\outbound\aeat\sede\_censo.py:49` | adapters | _CADASTRAL_RE: Final = re.compile(r"^0-9A-Z]{20}$") | 0 |
| `_CANONICAL_ANNUAL_RE` | `aeat\application\filing\_import.py:43` | application | _CANONICAL_ANNUAL_RE = re.compile(r"^\d{4}A$") | 0 |
| `_CANONICAL_MONTH_RE` | `aeat\application\filing\_import.py:42` | application | _CANONICAL_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]I1[0-2 | 0 |
| `_CANONICAL_MONTH_RE` | `aeat\application\filing\reconciliation\_reconcile.py:67` | application | _CANONICAL_MONTH_RE: Final[re.Pattern[str]] = re.compil | 0 |
| `_CANONICAL_QUARTER_RE` | `aeat\application\filing\_import.py:41` | application | _CANONICAL_QUARTER_RE = re.compile(r"^\d{4}Q[1-4]$") | 0 |
| `_CASILLA_EDIT_RE` | `aeat\application\review\_edit.py:50` | application | _CASILLA_EDIT_RE = re.compile(r"^casilla\.(?P<casilla_i | 0 |
| `_CASILLA_TAG_RE` | `aeat\domain\calculations\registry\_record_design.py:1242` | domain | _CASILLA_TAG_RE = re.compile(r"\[(\d{5})\]") | 0 |
| `_CASILLA_VALUE_RE` | `aeat\adapters\inbound\borrador\_extractors\modelo_100_summary_v2025.py:24` | adapters | _CASILLA_VALUE_RE = re.compile(     rf"(?m)^\s*(?P<casi | 0 |
| `_CELL_REF_PATTERN` | `aeat\domain\calculations\registry\_workbook_parity.py:67` | domain | _CELL_REF_PATTERN = re.compile(r"(?<![A-Z0-9_])(?:'[^'] | 0 |
| `_CELL_REF_VALUE_PATTERN` | `aeat\domain\calculations\registry\_workbook_parity.py:68` | domain | _CELL_REF_VALUE_PATTERN = re.compile(r"^(?:(?P<sheet>'[ | 0 |
| `_CERT_RE` | `aeat\adapters\outbound\aeat\sede\_notifications.py:66` | adapters | _CERT_RE: Final[re.Pattern[str]] = re.compile(r"^\d{10, | 0 |
| `_CIF_PATTERN` | `aeat\core\identity\_documents.py:59` | core | _CIF_PATTERN = re.compile(rf"^([{_CIF_KIND_LETTERS}])(\ | 0 |
| `_CIF_RE` | `aeat\adapters\outbound\aeat\auth\certificate.py:568` | adapters | _CIF_RE = re.compile(r"^[ABCDEFGHJNPQRSUVW]0-9]{7}0-9 | 0 |
| `_CLI_KEY_PATTERN` | `aeat\application\wizard\_translations.py:101` | application | _CLI_KEY_PATTERN = re.compile(r"quote(cli\.\w+(?:\.\w+) | 0 |
| `_CLI_OBJECT_KEY_ASSIGNMENT_PATTERN` | `aeat\core\redaction\__init__.py:95` | core | _CLI_OBJECT_KEY_ASSIGNMENT_PATTERN = re.compile(     r" | 0 |
| `_CLI_OBJECT_KEY_TOKEN_PATTERN` | `aeat\core\redaction\__init__.py:100` | core | _CLI_OBJECT_KEY_TOKEN_PATTERN = re.compile(     r"(?i)\ | 0 |
| `_CLI_UUID_PATTERN` | `aeat\core\redaction\__init__.py:91` | core | _CLI_UUID_PATTERN = re.compile(     r"\b0-9a-fA-F]{8}- | 0 |
| `_COMBINING_MARK_RE` | `aeat\domain\calculations\registry\_text.py:10` | domain | _COMBINING_MARK_RE = re.compile(r"[\u0300-\u036f]+") | 0 |
| `_COMPACT_PDF_CRLF_ROW_RE` | `aeat\domain\calculations\registry\_record_design.py:512` | domain | _COMPACT_PDF_CRLF_ROW_RE = re.compile(     r"^\s*(?P<or | 0 |
| `_COMPACT_PDF_ROW_RE` | `aeat\domain\calculations\registry\_record_design.py:508` | domain | _COMPACT_PDF_ROW_RE = re.compile(     r"^\s*(?P<ordinal | 0 |
| `_COTEJO_CSV` | `aeat\adapters\outbound\aeat\sede\_parse.py:46` | adapters | _COTEJO_CSV: Final[re.Pattern[str]] = re.compile(     r | 0 |
| `_COUNTRY_CODE_RE` | `aeat\domain\calculations\registry\_schema.py:261` | domain | _COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$") | 0 |
| `_CP_RE` | `aeat\adapters\inbound\pdf\_scrub.py:62` | adapters | _CP_RE = re.compile(r"\b(?:CP\s*IC\.P\.\s*)0-9]{5}\b") | 0 |
| `_CSV_AUTHENTICITY_FOOTER_RE` | `aeat\adapters\inbound\justificante\_extract.py:54` | adapters | _CSV_AUTHENTICITY_FOOTER_RE = re.compile(     r"mediant | 0 |
| `_CSV_FALLBACK_RE` | `aeat\adapters\inbound\justificante\_extract.py:69` | adapters | _CSV_FALLBACK_RE = re.compile(r"\bCSV\s*[=:]\s*([A-Z0-9 | 0 |
| `_CSV_LABEL_EN_RE` | `aeat\adapters\inbound\justificante\_extract.py:62` | adapters | _CSV_LABEL_EN_RE = re.compile(     r"Secure\s+Verificat | 0 |
| `_CSV_LABEL_INVERTED_RE` | `aeat\adapters\inbound\justificante\_extract.py:44` | adapters | _CSV_LABEL_INVERTED_RE = re.compile(     r"\b([A-Z0-9]{ | 0 |
| `_CSV_LABEL_RE` | `aeat\adapters\inbound\justificante\_extract.py:37` | adapters | _CSV_LABEL_RE = re.compile(     r"C[óo]digo\s+Seguro\s+ | 0 |
| `_CSV_PATTERN` | `aeat\adapters\outbound\aeat\sede\_schema.py:42` | adapters | _CSV_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A | 0 |
| `_CSV_RE` | `aeat\adapters\inbound\borrador\_detect.py:19` | adapters | _CSV_RE = re.compile(r"C[óo]digo\s+Seguro\s+de\s+Verifi | 0 |
| `_CSV_RE` | `aeat\adapters\inbound\borrador\_extractors\modelo_100_summary_v2025.py:31` | adapters | _CSV_RE = re.compile(     r"C[óo]digo\s+Seguro\s+de\s+V | 0 |
| `_CSV_RE` | `aeat\adapters\inbound\pdf\_scrub.py:53` | adapters | _CSV_RE = re.compile(r"\b(?P<csv>[A-Z0-9]{16})\b") | 0 |
| `_CSV_SHAPE_RE` | `aeat\adapters\outbound\aeat\sede\_declarations.py:135` | adapters | _CSV_SHAPE_RE = re.compile(r"^[A-Z0-9]{8,24}$") | 0 |
| `_CSV_SYNTHETIC_RE` | `aeat\adapters\inbound\justificante\test_corpus_sidecar_roundtrip.py:56` | adapters | _CSV_SYNTHETIC_RE = re.compile(r"^SANITIZED(\d{3})(\d{4 | 0 |
| `_DATE_DDMMAAAA_RE` | `aeat\domain\calculations\registry\_schema.py:488` | domain | _DATE_DDMMAAAA_RE = re.compile(r"^(0[1-9]I[12]\dI3[01]) | 0 |
| `_DATE_DDMMYYYY_RE` | `aeat\core\parsing\_dates.py:31` | core | _DATE_DDMMYYYY_RE: Final = re.compile(r"^\s*(\d{2}[-/]\ | 0 |
| `_DATE_ISO_RE` | `aeat\domain\calculations\registry\_schema.py:489` | domain | _DATE_ISO_RE = re.compile(r"^\d{4}-(0[1-9]I1[0-2])-(0[1 | 0 |
| _(+152 more)_ | | | | |

### TypeAdapter instances
Count: 21

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `_ANY_HTTP_URL_ADAPTER` | `aeat\adapters\outbound\aeat\sede\_iva_compensation_wallet.py:47` | adapters | _ANY_HTTP_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAd | 0 |
| `_BIC` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:162` | domain | _BIC = TypeAdapter(BicString) | 0 |
| `_BINDING_ID_ADAPTER` | `aeat\entrypoints\cli\_modelo.py:96` | entrypoints | _BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(Bin | 0 |
| `_CASILLA_ID_ADAPTER` | `aeat\entrypoints\cli\_modelo.py:97` | entrypoints | _CASILLA_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(Cas | 0 |
| `_CCAA` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:98` | domain | _CCAA = TypeAdapter(CCAACode) | 0 |
| `_CHAPTERS_ADAPTER` | `aeat\domain\manuals\_loader.py:83` | domain | _CHAPTERS_ADAPTER: TypeAdapter[tuple[Chapter, ...]] = T | 0 |
| `_COUNTRY_ADAPTER` | `aeat\domain\calculations\registry\test_country_code_data_type.py:20` | domain | _COUNTRY_ADAPTER: TypeAdapter[str] = TypeAdapter(Countr | 0 |
| `_DATE` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:182` | domain | _DATE = TypeAdapter(CalendarDate) | 0 |
| `_HTTP_URL_ADAPTER` | `aeat\domain\categories\_proportionality.py:68` | domain | _HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl) | 0 |
| `_IBAN_ADAPTER` | `aeat\domain\calculations\registry\test_iban_data_type.py:19` | domain | _IBAN_ADAPTER: TypeAdapter[str] = TypeAdapter(IbanStrin | 0 |
| `_MUNI` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:146` | domain | _MUNI = TypeAdapter(MunicipalityCode) | 0 |
| `_NAME` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:57` | domain | _NAME = TypeAdapter(PersonOrEntityName) | 0 |
| `_NIFIVA` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:77` | domain | _NIFIVA = TypeAdapter(NifIvaString) | 0 |
| `_NIF_ADAPTER` | `aeat\domain\calculations\registry\test_nif_data_type.py:27` | domain | _NIF_ADAPTER: TypeAdapter[str] = TypeAdapter(NifString) | 0 |
| `_PERIOD_ADAPTER` | `aeat\domain\calculations\registry\test_period_code_data_type.py:24` | domain | _PERIOD_ADAPTER: TypeAdapter[str] = TypeAdapter(PeriodC | 0 |
| `_POSTAL` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:130` | domain | _POSTAL = TypeAdapter(PostalCode) | 0 |
| `_PROV` | `aeat\domain\calculations\registry\test_long_tail_data_types.py:114` | domain | _PROV = TypeAdapter(ProvinceCode) | 0 |
| `_REVIEW_ITEM_ADAPTER` | `aeat\application\review\test_models.py:42` | application | _REVIEW_ITEM_ADAPTER: TypeAdapter[ReviewItem] = TypeAda | 0 |
| `_URL_ADAPTER` | `aeat\adapters\outbound\aeat\browser\_site_health.py:126` | adapters | _URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(Any | 5 |
| `_URL_ADAPTER` | `aeat\domain\portals\_entries\_common.py:22` | domain | _URL_ADAPTER: TypeAdapter[HttpUrl] = TypeAdapter(HttpUr | 5 |
| `_YEAR_ADAPTER` | `aeat\domain\calculations\registry\test_year_data_type.py:23` | domain | _YEAR_ADAPTER: TypeAdapter[int] = TypeAdapter(ModeloYea | 0 |

### Sentinel object() instances
Count: 0

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |

### SecureObjectNamespaceDefinition constants (UPPER_SNAKE_CASE)
Count: 37

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `AEAT_BROWSER_SESSION_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:448` | adapters | AEAT_BROWSER_SESSION_NAMESPACE = SecureObjectNamespaceD | 2 |
| `AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:520` | adapters | AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE = SecureObje | 2 |
| `AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:529` | adapters | AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE = SecureO | 2 |
| `AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:538` | adapters | AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE = SecureObjectNa | 2 |
| `APPLICATION_EVIDENCE_BUNDLE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:343` | adapters | APPLICATION_EVIDENCE_BUNDLE_NAMESPACE = SecureObjectNam | 4 |
| `APPLICATION_FILING_HISTORY_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:278` | adapters | APPLICATION_FILING_HISTORY_NAMESPACE = SecureObjectName | 2 |
| `ATTACHMENT_BLOB_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:430` | adapters | ATTACHMENT_BLOB_NAMESPACE = SecureObjectNamespaceDefini | 2 |
| `ATTACHMENT_MANIFEST_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:439` | adapters | ATTACHMENT_MANIFEST_NAMESPACE = SecureObjectNamespaceDe | 1 |
| `AUTH_APODERADO_CONFIGURATION_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:287` | adapters | AUTH_APODERADO_CONFIGURATION_NAMESPACE = SecureObjectNa | 2 |
| `CALCULATION_OBSERVATIONS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:296` | adapters | CALCULATION_OBSERVATIONS_NAMESPACE = SecureObjectNamesp | 2 |
| `CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:457` | adapters | CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE = SecureObjectNamespa | 3 |
| `GOOGLE_DRIVE_CONFIG_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:493` | adapters | GOOGLE_DRIVE_CONFIG_NAMESPACE = SecureObjectNamespaceDe | 2 |
| `GOOGLE_OAUTH_CLIENT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:466` | adapters | GOOGLE_OAUTH_CLIENT_NAMESPACE = SecureObjectNamespaceDe | 2 |
| `GOOGLE_OAUTH_METADATA_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:484` | adapters | GOOGLE_OAUTH_METADATA_NAMESPACE = SecureObjectNamespace | 2 |
| `GOOGLE_OAUTH_TOKEN_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:475` | adapters | GOOGLE_OAUTH_TOKEN_NAMESPACE = SecureObjectNamespaceDef | 2 |
| `IVA_COMPENSATION_HISTORY_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:323` | adapters | IVA_COMPENSATION_HISTORY_NAMESPACE = SecureObjectNamesp | 2 |
| `IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:305` | adapters | IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE = SecureO | 2 |
| `IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:314` | adapters | IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE = S | 2 |
| `LEDGER_CLASSIFICATION_RULES_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:352` | adapters | LEDGER_CLASSIFICATION_RULES_NAMESPACE = SecureObjectNam | 2 |
| `LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:361` | adapters | LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE = SecureObjectName | 1 |
| `LIVE_CENSUS_SNAPSHOT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:370` | adapters | LIVE_CENSUS_SNAPSHOT_NAMESPACE = SecureObjectNamespaceD | 3 |
| `LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:403` | adapters | LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE = SecureObjectNames | 4 |
| `LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:332` | adapters | LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE = SecureOb | 2 |
| `LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:412` | adapters | LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE = SecureObjectNam | 4 |
| `LIVE_VERIFY_OBSERVATION_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:421` | adapters | LIVE_VERIFY_OBSERVATION_NAMESPACE = SecureObjectNamespa | 4 |
| `LLM_CACHE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:502` | adapters | LLM_CACHE_NAMESPACE = SecureObjectNamespaceDefinition(  | 2 |
| `LLM_USAGE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:511` | adapters | LLM_USAGE_NAMESPACE = SecureObjectNamespaceDefinition(  | 3 |
| `PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:259` | adapters | PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE = SecureOb | 2 |
| `PROFILE_ASSETS_LEDGER_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:249` | adapters | PROFILE_ASSETS_LEDGER_NAMESPACE = SecureObjectNamespace | 2 |
| `PROFILE_INVENTORY_LEDGER_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:239` | adapters | PROFILE_INVENTORY_LEDGER_NAMESPACE = SecureObjectNamesp | 4 |
| `REPAIR_INTEGRITY_DECISION_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:269` | adapters | REPAIR_INTEGRITY_DECISION_NAMESPACE = SecureObjectNames | 2 |
| `TEST_SESSION_LIFECYCLE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:391` | adapters | TEST_SESSION_LIFECYCLE_NAMESPACE = SecureObjectNamespac | 2 |
| `TEST_SNAPSHOT_BASE_PROBE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:379` | adapters | TEST_SNAPSHOT_BASE_PROBE_NAMESPACE = SecureObjectNamesp | 2 |
| `USER_PROFILE_SNAPSHOT_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:230` | adapters | USER_PROFILE_SNAPSHOT_NAMESPACE = SecureObjectNamespace | 4 |
| `USER_PROFILE_VALUE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:221` | adapters | USER_PROFILE_VALUE_NAMESPACE = SecureObjectNamespaceDef | 8 |
| `WORKFLOW_RUN_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:212` | adapters | WORKFLOW_RUN_NAMESPACE = SecureObjectNamespaceDefinitio | 1 |
| `WORKFLOW_STATE_NAMESPACE` | `aeat\adapters\persistence\storage\_namespace_registry.py:202` | adapters | WORKFLOW_STATE_NAMESPACE = SecureObjectNamespaceDefinit | 8 |

### AnyUrl / URL constants (UPPER_SNAKE_CASE)
Count: 5

| Name | File:Line | Layer | Value (truncated) | Consumers |
| --- | --- | --- | --- | --- |
| `AEAT_GROI_URL` | `aeat\domain\calculations\registry\_groi_oracle.py:64` | domain | AEAT_GROI_URL = AnyUrl(Settings.external_constants().ae | 5 |
| `AEAT_NIF_IVA_ENTRY_URL` | `aeat\domain\calculations\registry\_aeat_nif_iva_oracle.py:50` | domain | AEAT_NIF_IVA_ENTRY_URL = AnyUrl(f"{_EXTERNAL.aeat.domai | 3 |
| `AEAT_NIF_IVA_VERIFICATION_URL` | `aeat\domain\calculations\registry\_aeat_nif_iva_oracle.py:44` | domain | AEAT_NIF_IVA_VERIFICATION_URL = AnyUrl(_EXTERNAL.aeat.o | 3 |
| `RENTA_WEB_OPEN_APP_URL` | `aeat\domain\calculations\registry\_renta_web_open_oracle.py:25` | domain | RENTA_WEB_OPEN_APP_URL = AnyUrl(_EXTERNAL.aeat.oracles. | 3 |
| `RENTA_WEB_OPEN_LANDING_URL` | `aeat\domain\calculations\registry\_renta_web_open_oracle.py:24` | domain | RENTA_WEB_OPEN_LANDING_URL = AnyUrl(f"{_EXTERNAL.aeat.d | 2 |


### _STRICT_FROZEN ConfigDict pattern (106 declarations)

ConfigDict(strict=True, frozen=True, extra=forbid) re-declared identically
in 106 files across adapters, domain, application, core layers.
Highest-cardinality multi-declaration. No canonical source in core/ today.

### _REGISTRY_ROOT bundled_path pattern (44 declarations, test-local)

_REGISTRY_ROOT = bundled_path(registry, aeat) re-declared in 44 test files.
Production code routes through ValidatedRegistryAuthority.

### _BUCKET_ID (29 declarations, test-local)

Per-test fixture constant. Not a candidate for centralisation.

## 2. Cross-domain coupling matrix

| From layer | To layer | Instances |
| --- | --- | --- |
| adapters | application | 47 |
| core | adapters | 43 |
| core | application | 37 |
| core | domain | 27 |
| domain | application | 24 |
| tests | adapters | 24 |
| core | entrypoints | 21 |
| domain | adapters | 15 |
| entrypoints | domain | 10 |
| tests | domain | 9 |
| entrypoints | adapters | 8 |
| tests | application | 8 |
| adapters | entrypoints | 7 |
| tests | entrypoints | 7 |
| tests | core | 7 |
| entrypoints | core | 6 |
| application | entrypoints | 4 |
| domain | entrypoints | 4 |
| entrypoints | application | 4 |
| application | adapters | 3 |
| application | core | 2 |
| core | test_coverage_inventory.py | 2 |
| core | test_hardcoded_constants_inventory.py | 2 |
| core | test_roundtrip_coverage.py | 2 |
| core | test_semantic_intent_sampler.py | 2 |
| core | tests | 2 |
| core | locales | 2 |
| application | diagnostics | 1 |
| entrypoints | test_coverage_inventory.py | 1 |
| entrypoints | test_hardcoded_constants_inventory.py | 1 |
| entrypoints | test_roundtrip_coverage.py | 1 |
| entrypoints | test_semantic_intent_sampler.py | 1 |
| entrypoints | tests | 1 |
| tests | test_coverage_inventory.py | 1 |
| tests | test_hardcoded_constants_inventory.py | 1 |
| tests | test_roundtrip_coverage.py | 1 |
| tests | test_semantic_intent_sampler.py | 1 |

## 3. Hexagonal direction violations (22 instances)

Constants flowing domain->adapters, domain->entrypoints,
or application->adapters against hexagonal discipline.

| Name | Direction | From file | To file |
| --- | --- | --- | --- |
| USER_PROFILE_VALUE_NAMESPACE | application->adapters | aeat\application\user_profile\_repository.py | aeat\adapters\persistence\storage\__init__.py |
| USER_PROFILE_VALUE_NAMESPACE | application->adapters | aeat\application\user_profile\_repository.py | aeat\adapters\persistence\storage\master_key\_master_ke |
| USER_PROFILE_SNAPSHOT_NAMESPACE | application->adapters | aeat\application\user_profile\_repository.py | aeat\adapters\persistence\storage\__init__.py |
| AEAT_NIF_IVA_VERIFICATION_URL | domain->adapters | aeat\domain\calculations\registry\_aeat_nif_iva_oracle. | aeat\adapters\outbound\aeat\sede\_nif_iva_check.py |
| AEAT_NIF_IVA_VERIFICATION_URL | domain->adapters | aeat\domain\calculations\registry\_aeat_nif_iva_oracle. | aeat\adapters\outbound\aeat\sede\test_nif_iva_check.py |
| AEAT_NIF_IVA_ENTRY_URL | domain->adapters | aeat\domain\calculations\registry\_aeat_nif_iva_oracle. | aeat\adapters\outbound\aeat\sede\_nif_iva_check.py |
| AEAT_NIF_IVA_ENTRY_URL | domain->adapters | aeat\domain\calculations\registry\_aeat_nif_iva_oracle. | aeat\adapters\outbound\aeat\sede\test_nif_iva_check.py |
| GROI_ORACLE_ID | domain->adapters | aeat\domain\calculations\registry\_groi_oracle.py | aeat\adapters\outbound\aeat\sede\test_groi_check.py |
| AEAT_GROI_URL | domain->adapters | aeat\domain\calculations\registry\_groi_oracle.py | aeat\adapters\outbound\aeat\sede\_groi_check.py |
| AEAT_GROI_URL | domain->adapters | aeat\domain\calculations\registry\_groi_oracle.py | aeat\adapters\outbound\aeat\sede\test_groi_check.py |
| AEAT_GROI_URL | domain->adapters | aeat\domain\calculations\registry\_groi_oracle.py | aeat\adapters\outbound\aeat\sede\test_groi_check_live.p |
| AEAT_WRITE_FORBIDDEN_VERB_TOKENS | domain->adapters | aeat\domain\calculations\registry\_remote_state_guard.p | aeat\adapters\outbound\aeat\sede\_renta_web_open_safety |
| AEAT_WRITE_FORBIDDEN_VERB_TOKENS | domain->adapters | aeat\domain\calculations\registry\_remote_state_guard.p | aeat\adapters\outbound\aeat\sede\test_renta_web_open_sa |
| RENTA_WEB_OPEN_APP_URL | domain->adapters | aeat\domain\calculations\registry\_renta_web_open_oracl | aeat\adapters\outbound\aeat\sede\_renta_web_open.py |
| RENTA_WEB_OPEN_APP_URL | domain->adapters | aeat\domain\calculations\registry\_renta_web_open_oracl | aeat\adapters\outbound\aeat\sede\test_renta_web_open.py |
| CATEGORY_FAMILY_MEMBERS | domain->entrypoints | aeat\domain\categories\_spending_category.py | aeat\entrypoints\cli\_ledger.py |
| M347_THRESHOLD_EUR | domain->entrypoints | aeat\domain\modelos\_row_models.py | aeat\entrypoints\cli\_modelo.py |
| _URL_ADAPTER | domain->adapters | aeat\domain\portals\_entries\_common.py | aeat\adapters\outbound\aeat\browser\_site_health_parser |
| _URL_ADAPTER | domain->adapters | aeat\domain\portals\_entries\_common.py | aeat\adapters\outbound\aeat\browser\session.py |
| _URL_ADAPTER | domain->adapters | aeat\domain\portals\_entries\_common.py | aeat\adapters\outbound\aeat\browser\test_site_health.py |
| PORTAL_REGISTRY | domain->entrypoints | aeat\domain\portals\_registry.py | aeat\entrypoints\cli\_app_live.py |
| PORTAL_REGISTRY | domain->entrypoints | aeat\domain\portals\_registry.py | aeat\entrypoints\cli\test_live_portals_verbs.py |

## 4. Same-name multi-declaration list (top 30)

| Name | Declaration count | Layers |
| --- | --- | --- |
| _STRICT_FROZEN | 106 | adapters, application, core, domain |
| _REGISTRY_ROOT | 44 | application, domain, entrypoints |
| ENTRY | 42 | domain |
| _BUCKET_ID | 29 | adapters, application, domain, entrypoints |
| _LOGGER | 14 | adapters, application, domain, entrypoints |
| _EXTERNAL | 12 | adapters, domain |
| _T0 | 12 | application, domain, entrypoints |
| _SRC_ROOT | 10 | core, domain, test_cast_rationale_inventory.py, test_clock_enrollment_inventory.py, test_coverage_inventory.py, test_decimal_enrollment_inventory.py, test_hardcoded_constants_inventory.py, test_parsing_enrollment_inventory.py, test_semantic_intent_sampler.py, test_utc_validator_enrollment_inventory.py |
| _T1 | 9 | application, domain, entrypoints |
| _PROFILE_ID | 9 | core, entrypoints |
| _FIXTURES | 8 | adapters, application, tests |
| _NOW | 8 | adapters, application, domain, entrypoints |
| _HEX_64_PATTERN | 8 | application, core, domain |
| _RUNNER | 8 | entrypoints, tests |
| _REPO_ROOT | 7 | core, domain, test_mock_inventory.py, test_monkeypatch_inventory.py, test_no_skip_xfail.py, test_no_tautology.py, tests |
| _PERIOD_RE | 6 | adapters, application, domain, entrypoints |
| _ZERO | 6 | adapters, application, core, domain |
| _T2 | 6 | application, domain |
| _FIXTURES_DIR | 6 | test_mock_inventory.py, test_monkeypatch_inventory.py, test_no_skip_xfail.py, test_no_tautology.py, tests |
| _NIF_CANARY | 5 | adapters, core |
| _STORAGE_DEGRADATION_ERRORS | 5 | application |
| _PERIOD | 5 | application |
| _CLOCK | 5 | application |
| _CAPTURED_AT | 5 | application |
| _DECLARED_ERROR_CODES | 5 | core |
| _OBJECT_KEY | 5 | core, domain, entrypoints |
| _FORBIDDEN_REMOTE_ACTIONS | 5 | domain |
| _SRC_AEAT | 5 | test_mock_inventory.py, test_monkeypatch_inventory.py, test_no_skip_xfail.py, test_no_tautology.py, tests |
| _SEDE_BASE | 4 | adapters |
| _READ_GUARD_POLICY | 4 | adapters |

## 5. core/external_constants gap table

src/aeat/core/external_constants.py holds 13 constants.
259 cross-module constants live outside it. Top 80 by consumer count:

| Name | File:Line | Layer | Val type | Consumers |
| --- | --- | --- | --- | --- |
| PROJECT_ROOT | aeat\core\config.py:60 | core | Attribute | 37 |
| PROJECT_ROOT | aeat\core\paths.py:23 | core | Attribute | 37 |
| PROJECT_ROOT | aeat\entrypoints\cli\test_retired_cli_literals.py:9 | entrypoints | subscript | 37 |
| PROJECT_ROOT | aeat\tests\test_release_config.py:33 | tests | subscript | 37 |
| ERROR_REGISTRY | aeat\core\errors\_registry.py:164 | core | frozen:MappingProxyType | 31 |
| FIXTURES_DIR | aeat\adapters\inbound\justificante\test_parser.py:31 | adapters | binop | 22 |
| FIXTURES_DIR | aeat\tests\__init__.py:18 | tests | binop | 22 |
| SUPPORTED_OUTPUT_LANGUAGES | aeat\core\i18n\_render.py:29 | core | tuple-literal | 12 |
| KEY_SIZE | aeat\adapters\persistence\storage\crypto\_crypto.py:38 | adapters | int | 11 |
| IVA_COMPENSATION_WALLET_URL | aeat\adapters\outbound\aeat\sede\_iva_compensation_wallet.py:64 | adapters | Name | 9 |
| REQUIRED_SCOPES | aeat\adapters\outbound\google\_records.py:36 | adapters | tuple-literal | 9 |
| SETUP_FLOW | aeat\application\wizard\_catalogue.py:837 | application | call:WizardFlow | 9 |
| BUCKETS_DIRNAME | aeat\adapters\persistence\storage\_namespace_registry.py:19 | adapters | str | 8 |
| WORKFLOW_STATE_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:202 | adapters | call:SecureObjectNamespaceDefinition | 8 |
| USER_PROFILE_VALUE_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:221 | adapters | call:SecureObjectNamespaceDefinition | 8 |
| STORAGE_NAMESPACE_REGISTRY | aeat\adapters\persistence\storage\_namespace_registry.py:737 | adapters | call:StorageHierarchyRegistry | 8 |
| USER_PROFILE_VALUE_NAMESPACE | aeat\application\user_profile\_repository.py:44 | application | Attribute | 8 |
| PORTAL_REGISTRY | aeat\domain\portals\_registry.py:194 | domain | call:_finalise_registry | 8 |
| CERTIFICATE_CONTEXT_MARKER | aeat\adapters\outbound\aeat\auth\_certificate_backends\_base:18 | adapters | str | 7 |
| GROI_ORACLE_ID | aeat\domain\calculations\registry\_groi_oracle.py:60 | domain | str | 6 |
| AEAT_WRITE_FORBIDDEN_ACTIONS | aeat\domain\calculations\registry\_remote_state_guard.py:36 | domain | tuple-literal | 6 |
| _URL_ADAPTER | aeat\adapters\outbound\aeat\browser\_site_health.py:126 | adapters | TypeAdapter | 5 |
| BUCKET_DB_DIRNAME | aeat\adapters\persistence\storage\_namespace_registry.py:20 | adapters | str | 5 |
| WIZARD_FLOWS | aeat\application\wizard\_catalogue.py:857 | application | tuple-literal | 5 |
| ORACLE_ID | aeat\domain\calculations\registry\_aeat_nif_iva_oracle.py:41 | domain | str | 5 |
| AEAT_GROI_URL | aeat\domain\calculations\registry\_groi_oracle.py:64 | domain | call:AnyUrl | 5 |
| _URL_ADAPTER | aeat\domain\portals\_entries\_common.py:22 | domain | TypeAdapter | 5 |
| ELIGIBLE_USAGE_RATIO_CATEGORIES | aeat\domain\usage_ratios\_model.py:50 | domain | call:_eligible_categories | 5 |
| SPANISH_AMOUNT_GROUP | aeat\adapters\inbound\pdf\_label_regex.py:35 | adapters | str | 4 |
| AEAT_SESSION_IDLE_TTL | aeat\adapters\outbound\aeat\auth\_authenticator.py:84 | adapters | call:timedelta | 4 |
| CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE | aeat\adapters\outbound\aeat\auth\_clave_movil.py:83 | adapters | str | 4 |
| USER_PROFILE_SNAPSHOT_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:230 | adapters | call:SecureObjectNamespaceDefinition | 4 |
| PROFILE_INVENTORY_LEDGER_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:239 | adapters | call:SecureObjectNamespaceDefinition | 4 |
| APPLICATION_EVIDENCE_BUNDLE_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:343 | adapters | call:SecureObjectNamespaceDefinition | 4 |
| LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:403 | adapters | call:SecureObjectNamespaceDefinition | 4 |
| LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:412 | adapters | call:SecureObjectNamespaceDefinition | 4 |
| LIVE_VERIFY_OBSERVATION_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:421 | adapters | call:SecureObjectNamespaceDefinition | 4 |
| USER_PROFILE_SNAPSHOT_NAMESPACE | aeat\application\user_profile\_repository.py:45 | application | Attribute | 4 |
| CLI_PROFILE_ID_PLACEHOLDER | aeat\core\redaction\__init__.py:87 | core | str | 4 |
| AEAT_WRITE_FORBIDDEN_VERB_TOKENS | aeat\domain\calculations\registry\_remote_state_guard.py:70 | domain | frozen:frozenset | 4 |
| TX_BUCKET_NAMESPACE | aeat\domain\transactions\_repository.py:28 | domain | str | 4 |
| CSV_EXTENSIONS | aeat\adapters\inbound\financial\providers\_constants.py:21 | adapters | frozen:frozenset | 3 |
| G313_LAUNCHER_URL | aeat\adapters\outbound\aeat\sede\_censo_live.py:54 | adapters | fstring | 3 |
| PRE303_PRESENTATION_SERVICE_URL | aeat\adapters\outbound\aeat\sede\_iva_compensation_wallet.py:65 | adapters | Name | 3 |
| REMOTE_MIRROR_MANIFEST_NAMESPACE | aeat\adapters\outbound\storage\_mirror_manifest.py:20 | adapters | str | 3 |
| BUCKET_MANIFEST_FILENAME | aeat\adapters\persistence\storage\_namespace_registry.py:23 | adapters | str | 3 |
| BUCKET_LOCK_FILENAME | aeat\adapters\persistence\storage\_namespace_registry.py:24 | adapters | str | 3 |
| BUCKET_DEK_FILENAME | aeat\adapters\persistence\storage\_namespace_registry.py:26 | adapters | str | 3 |
| BLOB_MANIFEST_SCHEMA_VERSION | aeat\adapters\persistence\storage\_namespace_registry.py:27 | adapters | int | 3 |
| LIVE_CENSUS_SNAPSHOT_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:370 | adapters | call:SecureObjectNamespaceDefinition | 3 |
| CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:457 | adapters | call:SecureObjectNamespaceDefinition | 3 |
| LLM_USAGE_NAMESPACE | aeat\adapters\persistence\storage\_namespace_registry.py:511 | adapters | call:SecureObjectNamespaceDefinition | 3 |
| NONCE_SIZE | aeat\adapters\persistence\storage\crypto\_crypto.py:32 | adapters | int | 3 |
| GCM_TAG_SIZE | aeat\adapters\persistence\storage\crypto\_crypto.py:35 | adapters | int | 3 |
| ACCEPTED_SOURCE_KINDS | aeat\application\aggregation\_service.py:49 | application | tuple-literal | 3 |
| BORRADOR_100_SNAPSHOT_NAMESPACE | aeat\application\live\_borrador_100.py:42 | application | Attribute | 3 |
| CANONICAL_CRUD_VERBS | aeat\application\operator_surface\_crud_contract.py:37 | application | frozen:frozenset | 3 |
| OUTPUT_LANGUAGE_ENV_VAR | aeat\core\i18n\_render.py:27 | core | str | 3 |
| RUN_CONTEXT_VAR | aeat\core\observability\_context.py:86 | core | call:ContextVar | 3 |
| STEP_CONTEXT_VAR | aeat\core\observability\_context.py:92 | core | call:ContextVar | 3 |
| CLI_BUCKET_ID_PLACEHOLDER | aeat\core\redaction\__init__.py:88 | core | str | 3 |
| CLI_OBJECT_KEY_PLACEHOLDER | aeat\core\redaction\__init__.py:89 | core | str | 3 |
| AEAT_NIF_IVA_VERIFICATION_URL | aeat\domain\calculations\registry\_aeat_nif_iva_oracle.py:44 | domain | call:AnyUrl | 3 |
| AEAT_NIF_IVA_ENTRY_URL | aeat\domain\calculations\registry\_aeat_nif_iva_oracle.py:50 | domain | call:AnyUrl | 3 |
| M210_DEFERRED_TIPO_SENTINEL | aeat\domain\calculations\registry\_formula_runtime.py:55 | domain | Name | 3 |
| M210_CONVENIO_MISSING_SENTINEL | aeat\domain\calculations\registry\_formula_runtime.py:56 | domain | Name | 3 |
| M210_NOT_YET_AUTHORED_SENTINEL | aeat\domain\calculations\registry\_formula_runtime.py:57 | domain | Name | 3 |
| RENTA_WEB_OPEN_APP_URL | aeat\domain\calculations\registry\_renta_web_open_oracle.py:25 | domain | call:AnyUrl | 3 |
| KNOWN_VERIFICATION_PREDICATE_OPERATORS | aeat\domain\calculations\registry\_schema.py:2382 | domain | frozen:frozenset | 3 |
| CATEGORY_FAMILY_MEMBERS | aeat\domain\categories\_spending_category.py:101 | domain | dict-literal | 3 |
| M347_THRESHOLD_EUR | aeat\domain\modelos\_row_models.py:276 | domain | call:Decimal | 3 |
| RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS | aeat\domain\renta\_ledger_expenses.py:34 | domain | Name | 3 |
| MINIMUM_CLASSIFICATION_TIER | aeat\domain\transactions\_model_tier.py:92 | domain | Attribute | 3 |
| _FIXTURES_ROOT | aeat\adapters\outbound\aeat\browser\test_session.py:21 | adapters | binop | 2 |
| _FIXTURES_ROOT | aeat\adapters\outbound\aeat\browser\test_site_health.py:39 | adapters | binop | 2 |
| PLAYWRIGHT_WAIT_DOMCONTENTLOADED | aeat\adapters\outbound\aeat\sede\_browser_constants.py:15 | adapters | str | 2 |
| PLAYWRIGHT_WAIT_NETWORKIDLE | aeat\adapters\outbound\aeat\sede\_browser_constants.py:19 | adapters | str | 2 |
| DRIVE_FILE_SCOPE | aeat\adapters\outbound\google\_records.py:34 | adapters | Attribute | 2 |
| SHEETS_SCOPE | aeat\adapters\outbound\google\_records.py:35 | adapters | Attribute | 2 |
| _LEDGER_OBJECT_KEY | aeat\adapters\persistence\profile\assets.py:31 | adapters | str | 2 |

### Currently registered in core/external_constants.py

| Name |
| --- |
| BINARY_MIME_TYPE |
| CLASSIFIED_BY_MANUAL |
| CSV_ENCODING_FALLBACK_CHAIN |
| CSV_MIME_TYPE |
| DEFAULT_CURRENCY |
| JSON_MIME_TYPE |
| LATIN_1_ENCODING |
| PDF_EXTENSION |
| PDF_MIME_TYPE |
| PROVENANCE_SOURCE_MANUAL_CLI |
| XLSM_EXTENSION |
| XLSX_EXTENSION |
| XLS_EXTENSION |

## Module(s)

All 1,655 .py files under src/aeat/. Primary reference files:

- src/aeat/core/external_constants.py -- existing centralisation target (13 constants)
- src/aeat/adapters/persistence/storage/_namespace_registry.py -- 37 UPPER namespace constants, all cross-module
- src/aeat/domain/calculations/registry/_remote_state_guard.py -- AEAT_WRITE_FORBIDDEN_* constants
- src/aeat/core/errors/_registry.py -- ERROR_REGISTRY MappingProxyType (31 consumers)
- src/aeat/core/i18n/_render.py -- SUPPORTED_OUTPUT_LANGUAGES, OUTPUT_LANGUAGE_ENV_VAR
- src/aeat/adapters/persistence/storage/crypto/_crypto.py -- KEY_SIZE, NONCE_SIZE, GCM_TAG_SIZE
- src/aeat/domain/calculations/registry/_groi_oracle.py -- GROI_ORACLE_ID, AEAT_GROI_URL
- src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py -- ORACLE_ID, AEAT_NIF_IVA_*
- src/aeat/domain/fincas/_amortization_ledger.py -- ART_23_1_F_RATE, DAYS_PER_YEAR
- src/aeat/domain/modelos/_row_models.py -- M347_THRESHOLD_EUR
- src/aeat/application/aggregation/_counterpart.py -- THRESHOLD_347_EUR (duplicate of M347_THRESHOLD_EUR)

## File(s)

- src/aeat/core/external_constants.py:1
- src/aeat/adapters/persistence/storage/_namespace_registry.py:19
- src/aeat/core/errors/_registry.py:164
- src/aeat/core/i18n/_render.py:27
- src/aeat/domain/calculations/registry/_remote_state_guard.py:36
- src/aeat/adapters/persistence/storage/crypto/_crypto.py:32
- src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py:41
- src/aeat/domain/calculations/registry/_groi_oracle.py:60
- src/aeat/domain/portals/_entries/_common.py:22
- src/aeat/domain/fincas/_amortization_ledger.py:30
- src/aeat/domain/modelos/_row_models.py:276
- src/aeat/application/aggregation/_counterpart.py:311

## Related

No prior vault documents for this feature.
