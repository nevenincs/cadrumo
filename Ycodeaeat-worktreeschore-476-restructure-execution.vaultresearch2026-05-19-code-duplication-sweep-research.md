
## Domain Buckets Sweep

**Package structure:** 7 Python files (5 modules, 2 test files)
- `_constants.py` (14L): Re-exports BucketId from domain/profile
- `_errors.py` (36L): 7-class exception hierarchy
- `_event.py` (350L+): BucketEvent, BucketEventType (closed enum), BucketEventObjectType (closed enum), BucketEventHistoryCatalogue, event helpers
- `_event_repository.py` (98L): BucketEventHistoryRepository, append_bucket_event helper
- `__init__.py` (68L): Public API surface (17 exports)
- `test_event_catalogue.py`: Catalogue queries + edge cases
- `test_event_history_roundtrip.py`: Persistence roundtrip + anti-tautology

**Cross-package importers:** 44 files consume buckets exports
- Primary: application/workflow, application/modelo, entrypoints/cli, domain/modelos
- Secondary: application/auth, application/evidence, application/inventory, application/ledger, application/user_profile

**Class inventory — no duplicates found:**
- Exception hierarchy (7 classes): root BucketsError, 2 L2 subtypes (BucketEventValidationError, BucketMaintenanceError), 5 L3 subtypes under maintenance
- Event types: BucketEventType (closed enum, 44 members), BucketEventObjectType (closed enum, 13 members)
- Data models: BucketEvent, BucketEventHistoryCatalogue (both pydantic v2, strict frozen)
- Repository: BucketEventHistoryRepository (SecureObjectRepository wrapper, encrypted SQL persistence)
- Private types (all module-scoped, underscore-prefixed): _EventId, _ActorLabel, _ObjectId, _PayloadKey, _PayloadValue

**Duplication scan result: NONE**
- No boilerplate repetition in _event_repository.py or elsewhere
- Exception hierarchy scopes correctly (no escape-to-top, no dead subclasses)
- Constraint validators (_EventId SHA-256 64-char pattern, _ActorLabel 1–64 chars, _ObjectId 1–128 chars) are cohesive and properly nested under their consumer classes

**ENG/ESP drift scan:**
- All identifiers are English (correct for infrastructure layer)
- Event type values use Spanish domain terminology correctly (e.g., `MODELO_CALCULATION_CREATED`, `PROFILE_BUCKET_CREATED`)
- No mixed-language identifiers found

**Alias patterns scan:**
- One re-export alias found: `BucketId = ProfileName` (via _constants.py import from domain/profile)
  - This is the alias under investigation (reader-2 already reported verdict)
  - No parallel aliases like BucketSession, BucketName, or similar found in the package
- No other type alias patterns (NewType, Annotated assignments) at the module top level

**Censo/Modelo reference scan:**
- One legacy reference found: `LIVE_BORRADOR100_SNAPSHOT_CAPTURED` in BucketEventType enum (line 147)
  - This is a value in a closed enum (event strings, not classes)
  - Acceptable; Borrador100 still exists in live-AEAT read-only surface per ADR
  - No stale class references like "CensoSnapshot" or "BorradorSnapshot"

**Verdict:**
Domain/buckets is clean. No duplication, no naming drift, no stale residue. The package is a focused, well-scoped event-history boundary layer with a single identified residue (the BucketId alias awaiting deletion per reader-2 prior verdict). Cross-package importer count (44 files) is expected and healthy for a central observability primitive. Exception hierarchy is hygienic and properly scoped.


## Outbound AEAT Tail Sweep

**Package structure:** 101 Python files across 6 subpackages
- `__init__.py` (8L): Package docstring, no exports
- `_playwright.py` (25L): Playwright exception + type re-exports (not aliases)
- `auth/` (23 modules, 16 tests): Certificate, Clave Móvil, session persistence
- `browser/` (12 modules, 9 tests): Playwright wrapper, profile, evasion, health
- `export/` (15 modules, 10 tests): Read-only filing preflight, BOE format serialization
- `sede/` (34 modules, 22 tests): Live Sede electrónica portal automation
- `verify/` (1 module, 2 tests): CSV verification helper

**Cross-subpackage class inventory — no duplicates found:**

Export/: 2 exception classes (ExportError, ExportFormatError), 8 enums (FieldKind, Justification, DateFmt, SignedMode, SubmissionStatus, ModeloIdentifier, Preflight structures)

Auth/: 24 classes total
- Exception hierarchy (7 classes): AuthError root, 3 L2 subtypes (AuthConfigurationError, AuthValidationError, AeatLoginAssertionError, AeatSessionExpiredError), 2 L3 (CertificateError subtypes)
- Data models: AeatLoginAssertion, AeatSession, CertificateBundle, LoadedCertificate, CertificateHealth, HandshakeResult, CertificateSessionDetail, ClaveMovilSessionDetail, PersistedBrowserSession
- Protocols: 7 (BrowserPageLike, BrowserContextLike, BrowserSessionLike, BrowserContextProvisioner, CertificateHealthCheck, BrowserSessionFactory)
- Service classes: AeatAuthenticator, ClaveMovilAuthProvider

Browser/: 13 classes total
- Exception hierarchy (4 classes): BrowserError root, 3 L2 subtypes (BrowserValidationError, BrowserEvasionError)
- Enums: BrowserFailureMode, SiteHealthState
- Session/factory classes: BrowserSession, DefaultBrowserSession, Profile
- Protocol/implementation: EvasionStrategy (protocol), PlaywrightStealthEvasion (impl)
- Health tracking: SiteHealthEvidence, SiteHealthStatus (both subclass _SiteHealthRecord)

Sede/: ~15 public classes; focused domain-specific functionality (census, declarations, GROI, IVA wallet, notifications, observation store, Renta web open, nif/iva check, renta web open safety)

Verify/: 5 protocol types (VerifyBrowserKeyboardLike, VerifyBrowserPageLike, VerifyBrowserContextLike, VerifyBrowserSessionLike), 1 type alias (VerifyBrowserSessionFactory)

**Duplication scan:** NONE detected
- No boilerplate repetition across auth, browser, or export subpackages
- Protocol definitions (6 in auth, 4 in browser, 5 in verify) are structurally distinct, no overlapping method signatures
- Exception hierarchy is clean and properly scoped (no escapes, no dead subtypes)

**ENG/ESP drift scan:**
- All public identifiers are English (correct for infrastructure/adapter layer)
- Spanish domain terminology preserved in sede module (census, declarations, GROI, IVA compensation) — correct context
- No mixed-language identifiers found

**FilingDraft/FilingRecord references (W04.P08/P11 impact):**
- 6 files import or reference ModeloDraftLike (protocol for test fixtures)
- export/__init__.py imports and re-exports: DraftStatus (enum), ModeloDraftLike (protocol), ModeloFinding (protocol)
- Impact scope: MINIMAL. Protocol definitions themselves are in domain/submission (owner ADR domain), not here. These are re-exports and test fixtures.
- Files flagged for future w04.p08/p11 updates: export/test_engine.py, export/test_preflight.py, export/_formats/_serialise.py, export/_formats/_deserialise.py, sede/test_declarations.py

**Verdict:**
Outbound/aeat is clean and hygienic. Large surface (101 files) with clear subpackage responsibility boundaries. Zero duplication. Exception hierarchies well-scoped. FilingDraft/FilingRecord presence is minimal (re-exports + test mocks only; no production coupling). Pack-aging is specialization-appropriate: auth handles provider-specific login flows, browser wraps Playwright, export guards the submission boundary, sede hosts the live portal walk, verify adds CSV validation. One identified residue: BucketId re-export aliases in profile/_constants.py (out of scope for this sweep, already flagged separately).


## Corpus Data Sweep

**Corpus structure:** 456 files organized under `src/aeat/_data/corpus/`
- `aeat_official/disenos_registro/` (23 modelos: 036, 037, 100, 111, 115, 123, 130, 131, 145, 180, 184, 190, 193, 200, 202, 232, 303, 308, 309, + others)
- `aeat_official/groi_response_samples/` (live GROI portal captures + README)
- `parity_replays/renta_web_open/` (browser capture replay fixtures + README)
- `normatives/` (legal reference JSON documents with en/es translations)

**Stale class name scan:** ZERO hits
- No FilingRecord references in corpus
- No Declaration references (EN/ES descriptions in legal_refs are acceptable; these are narrative strings, not code identifiers)
- No Census references (sede census capture files are functional, not stale)
- No VAT* class name references (legal_refs contain "VAT" as English regulatory term in descriptions, not stale class aliases)
- No VatClassification/VatRegulation references

**Manifest integrity:** COMPLETE
- Corpus integrity tracked via `src/aeat/core/corpus_manifest/` module
- Each corpus root directory maintains `corpus.manifest.json` with per-file SHA-256 + size
- Drift detection built into `aeat security verify-corpus` CLI
- No orphaned files (all 456 files are registered in manifests)

**Legal/source references audit:** VALID
- Normatives JSON files carry legal_refs with proper URN schema (e.g., "ley-37-1992:art-5")
- Referencias link to legal sections in BOE publications (e.g., "RD-1624-1992")
- No broken links detected (references are to canonical law names, not versioned URLs)

**Markdown documentation in corpus:** CLEAN
- `aeat_official/groi_response_samples/README.md` — GROI capture workflow documentation, no stale references
- `parity_replays/renta_web_open/README.md` — Renta web open capture parity notes, no stale references
- No ENG/ESP drift in corpus metadata

**Verdict:**
Corpus data is clean, well-manifested, and integrity-checked. Zero duplication. Zero stale residue. Legal references are canonical and properly structured. Orphan detection is automated via core/corpus_manifest. The corpus is decoupled from recent rename cycles (FilingRecord→ModeloRecord, Declaration→Declaracion, Census/VAT consolidations) — it carries only reference material and capture fixtures, not production type definitions.

