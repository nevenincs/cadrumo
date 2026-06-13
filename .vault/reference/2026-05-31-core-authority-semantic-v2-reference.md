---
tags:
  - '#reference'
  - '#core-authority-semantic-v2'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-enums-reference]]"
  - "[[2026-05-31-core-authority-duplicates-reference]]"
  - "[[2026-05-31-core-authority-constants-reference]]"
  - "[[2026-05-31-core-authority-import-map-reference]]"
---

# core-authority-semantic-v2 reference: semantic equivalence audit

Semantic-equivalence pairs across src/aeat/ detected via vaultspec-rag GPU-accelerated
dense/sparse hybrid search (106,932 codebase chunks, RTX 4080 SUPER, index date 2026-05-31).
Five categories: enums, constants, functions, error classes, protocols.
Cross-checked against AST-level core-authority-enums-reference (226 enum inventory) and
core-authority-duplicates-reference (name-collision list).

---

## Module(s)

src/aeat/core/, src/aeat/domain/, src/aeat/application/, src/aeat/adapters/, src/aeat/entrypoints/

## File(s)

All files listed in pair tables below.

## Related

- `2026-05-31-core-authority-enums-reference`
- `2026-05-31-core-authority-duplicates-reference`
- `2026-05-31-core-authority-constants-reference`
- `2026-05-31-core-authority-import-map-reference`

---

## Findings

### 1. Semantic Enum Pairs

#### PAIR E-01 - Severity triads (INFO / WARNING / ERROR)

Five independent re-declarations of the same three-member severity vocabulary.
The AST audit (enums-reference section 4) identified these as name-collision duplicates.
RAG confirms semantic identity: all five share the INFO < WARNING < ERROR ordering contract.

| Name | File:Line | Members |
|---|---|---|
| BaseSeverity | core/errors/_severity.py:20 | INFO WARNING ERROR |
| WizardCheckSeverity | application/wizard/_verifier.py:25 | OK WARNING ERROR (INFO renamed OK) |
| TransactionDiagnosticSeverity | application/transactions/_diagnostics.py:14 | INFO WARNING ERROR |
| OverviewStatus | application/overview/_status.py:12 | OK WARNING ERROR |
| UserProfileRegistryContractSeverity | domain/user_profile/_registry_contract.py:21 | INFO WARNING ERROR |
| CertificateHealthSeverity | adapters/outbound/aeat/auth/certificate.py:110 | INFO WARNING ERROR (+ CRITICAL) |

Overlap: 100% for four of six; WizardCheckSeverity/OverviewStatus use OK for INFO (80% match);
CertificateHealthSeverity adds CRITICAL (75% subset). Semantic role is identical.

Consolidation: delete all five re-declarations; callers import BaseSeverity from core/errors/_severity.py.
CertificateHealthSeverity.CRITICAL extends BaseSeverity or maps at the adapter boundary.

AST audit already listed this pair; RAG confirms.

---
#### PAIR E-02 - Parity-outcome triads (MATCH / MISMATCH / MISSING)

| Name | File:Line | Members |
|---|---|---|
| LiveParityKind | domain/calculations/registry/_live_parity.py:11 | MATCH MISMATCH MISSING |
| WorkbookParityKind | domain/calculations/registry/_workbook_parity.py:11 | MATCH MISMATCH MISSING |

Overlap: 100%. Same subdomain; only the data source differs (live oracle vs workbook).

Consolidation: declare ParityOutcome once at domain/calculations/registry/_parity.py.

AST audit listed this pair; RAG confirms.

---

#### PAIR E-03 - CCAA geographic duplicates

| Name | File:Line | Members |
|---|---|---|
| CCAA | domain/profile/_ccaa.py:56 | 01-17 (17 members) |
| CalendarCCAA | domain/deadlines/_festivos.py:59 | 01-17 (17 members) |

Overlap: 100%. CalendarCCAA is a pure copy with no new members.

Consolidation: delete CalendarCCAA; _festivos.py uses CCAA directly. Both relocate to core/geography.py.

AST audit listed this pair; RAG confirms.

---

#### PAIR E-04 - Submission lifecycle enums (same package, overlapping members)

| Name | File:Line | Members (count) |
|---|---|---|
| ModeloDraftStatus | domain/submission/_protocols.py:123 | BORRADOR VALIDADO LISTO_PARA_PRESENTAR APROBADO APROBACION_CADUCADA PRESENTADA ACEPTADA RECHAZADA ENMENDADO ANULADO (10) |
| SubmissionStatus | domain/submission/_models.py:22 | PENDIENTE_DE_PRESENTAR EN_TRAMITACION PRESENTADA ACEPTADA RECHAZADA FALLIDA (6) |

Shared members: PRESENTADA, ACEPTADA, RECHAZADA (50% overlap). Both cover adjacent slices of
the same real-world submission lifecycle. Divergence in the shared members is a latent bug surface.

Consolidation: merge into ModeloLifecycleStatus spanning the full arc, or introduce a shared base
with SubmissionStatus as a terminal sub-range.

NOT IN AST name-collision list -- SEMANTIC-ONLY FIND.

---

#### PAIR E-05 - Reconciliation verdict enums (Spanish vs English naming split)

| Name | File:Line | Members |
|---|---|---|
| ReconciliationStatus | application/filing/reconciliation/_schema.py:34 | COINCIDE DIVERGENTE NOT_YET_FOUND |
| ReconcileOutcome | application/modelo/_reconcile.py:12 | MATCH MISMATCH MISSING |

Overlap: 100% semantic (COINCIDE=MATCH, DIVERGENTE=MISMATCH, NOT_YET_FOUND=MISSING).
Same three-outcome shape split across two application subpackages with a Spanish/English naming split.

Consolidation: unify under ReconciliationOutcome with Spanish values in application/filing/reconciliation/;
delete ReconcileOutcome.

NOT IN AST name-collision list -- SEMANTIC-ONLY FIND.

---
#### PAIR E-06 - Snapshot/profile lifecycle status (plaintext mirror relationship)

| Name | File:Line | Members |
|---|---|---|
| UserProfileStatus | domain/user_profile/_values.py:100 | ACTIVE TOMBSTONED |
| BucketLifecycleStatus | adapters/persistence/storage/bucket/_manifest.py:76 | ACTIVE TOMBSTONED |
| SnapshotLifecycleState | application/live/_snapshot_base.py:70 | ACTIVE SUPERSEDED DISCARDED |

BucketLifecycleStatus is explicitly documented as a plaintext mirror of UserProfileStatus (100% overlap).
SnapshotLifecycleState shares only ACTIVE (33%) and is semantically distinct.

Consolidation: replace BucketLifecycleStatus with a mapping function from UserProfileStatus.
SnapshotLifecycleState remains separate.

BucketLifecycleStatus/UserProfileStatus pair NOT IN AST collision list -- SEMANTIC-ONLY FIND.

---

#### PAIR E-07 - Verification verdict enums (distinct concerns, NOT a consolidation candidate)

| Name | File:Line | Members |
|---|---|---|
| VerificationStatus | application/verification/_schema.py:47 | VERIFIED NEEDS_REVIEW |
| DeclaracionVerifyVerdict | application/filing/_export.py:77 | MATCH DRIFT MISSING |

Both surface operator-facing pass/fail results but for different pipeline concerns.
Not a consolidation candidate; document the boundary. Confidence: LOW.

---

### 2. Semantic Constant Pairs

#### PAIR C-01 - PROJECT_ROOT duplicate declaration

core/config.py:60 and core/paths.py:23 both declare Path to the repo root.
Canonical: core/paths.py. Remove from core/config.py. (AST audit confirmed.)

#### PAIR C-02 - SCHEMA_VERSION duplicate in profile submodules

domain/profile/inventory/__init__.py:34 and domain/profile/assets/__init__.py:20
both declare SCHEMA_VERSION = 1.
Rename to INVENTORY_SCHEMA_VERSION and ASSETS_SCHEMA_VERSION in-place. (AST audit confirmed.)

#### PAIR C-03 - AEAT URL module constants (five redundant copies)

domain/calculations/registry/ exposes AEAT_GROI_URL, AEAT_NIF_IVA_VERIFICATION_URL,
AEAT_NIF_IVA_ENTRY_URL as public constants consumed by adapter scrapers.
adapters/outbound/aeat/sede/_iva_compensation_wallet.py:64-65 exposes IVA_COMPENSATION_WALLET_URL
and PRE303_PRESENTATION_SERVICE_URL consumed by application/live/.
All five should be deleted; callers read from Settings.external_constants(). (AST audit confirmed.)

#### PAIR C-04 - _IVA_RATE_TO_VAT_KIND private mapping (incomplete copy)

domain/iva/_invoice_classification.py:63 (5 entries: RATE_0, RATE_4, RATE_10, RATE_21, EXEMPT) vs
domain/invoices/_enums.py:76 (3 entries: RATE_4, RATE_10, RATE_21 only).
The invoices copy omits RATE_0 and EXEMPT, creating a latent classification hole.
Canonical: expand domain/invoices/_enums.py to 5 entries; delete the copy in _invoice_classification.py.
(AST audit confirmed.)

#### PAIR C-05 - USER_PROFILE_*_NAMESPACE type shadow

Adapter layer declares as SecureObjectNamespaceDefinition; application layer redeclares as plain str,
shadowing the typed NamespaceDef. Application layer should import from the registry. (AST audit confirmed.)

---

### 3. Semantic Function Pairs

#### PAIR F-01 - _hash_file SHA-256 file hasher (three independent copies)

| Name | File:Line | Return type |
|---|---|---|
| _hash_file | core/corpus_manifest/__init__.py:155 | tuple[str, int] sha256_hex content_length |
| _hash_file | domain/calculations/registry/_workbook_parity.py:1000 | tuple[str, int] sha256_hex length |
| _hash_file | application/ledger/_evidence.py:108 | str sha256_hex only |

First two are structurally identical: stream file in 64 KiB chunks through hashlib.sha256.
Third returns only the hex string.

Consolidation: core/hashing.py exports hash_file(path) returning tuple[str, int].
application/ledger/_evidence.py uses index 0. Eliminates three maintenance copies.

NOT IN AST name-collision list (private names, filtered by convention). SEMANTIC-ONLY FIND.

---

#### PAIR F-02 - SHA-256 bytes-to-hex one-liners (five independent copies)

| Name | File:Line | Input |
|---|---|---|
| _compute_sha256 | adapters/inbound/financial/providers/_base.py:326 | bytes |
| _hex_digest | adapters/persistence/storage/blob_store/_blob_store.py:127 | bytes |
| _sha256_payload | application/filing/_review.py:548 | object JSON-serialised first |
| _evidence_ref | application/live/__init__.py:1022 | str UTF-8 encoded 12-char prefix |
| _sha256_prefix | core/redaction/__init__.py:130 | str UTF-8 encoded 8-char prefix |

First two: hashlib.sha256(data).hexdigest() verbatim. Last three add encoding or truncation.

Consolidation: core/hashing.py exports sha256_hex(data: bytes) -> str; domain functions wrap it.

NOT IN AST collision list -- SEMANTIC-ONLY FIND.

---

#### PAIR F-03 - _normalise_period private function (two identical copies)

| Name | File:Line |
|---|---|
| _normalise_period | application/filing/_import.py:143 |
| _normalise_period | application/filing/reconciliation/_reconcile.py:329 |

Same name, same transformation, in sibling modules within application/filing/.

Consolidation: extract to application/filing/_period.py; both files import from there.

NOT IN AST collision list (private functions, different subpackage dirs). SEMANTIC-ONLY FIND.

---

#### PAIR F-04 - NIF identity normalisation vs full validation

| Name | File:Line | Behaviour |
|---|---|---|
| validate_identity | core/identity/_documents.py:206 | Full parse + check-letter validation |
| _normalise_tax_identity | application/auth/_sessions.py:433 | strip().upper() only |

_normalise_tax_identity silently accepts malformed NIFs. Replace with validate_identity at call site.

NOT IN AST collision list -- SEMANTIC-ONLY FIND.

---

#### PAIR F-05 - Registry snapshot loading helpers (three independent call sites)

| Name | File:Line |
|---|---|
| _load_registry_snapshot | application/filing/__init__.py (lru_cache wrapped) |
| _load_snapshot | entrypoints/cli/_config/__init__.py |
| _registry_snapshot | adapters/inbound/declaracion/_parser.py |

All three call ValidatedRegistryAuthority.load(root).snapshot(modelo, period).
The cached application helper is closest to canonical; entrypoint and adapter bypass it.

Consolidation: entrypoint and adapter import from application/filing/__init__.py.

NOT IN AST collision list -- SEMANTIC-ONLY FIND.

---

### 4. Semantic Error-Class Pairs

#### PAIR ER-01 - ExportFormatError in two modules

| Name | File:Line |
|---|---|
| ExportFormatError | application/export/_errors.py:8 |
| ExportFormatError | adapters/outbound/aeat/export/_errors.py:12 |

Same name, different hierarchy roots. Adapter error subclasses application error,
or rename adapter to AeatExportFormatError. IN AST name-collision list; RAG confirms.

---

#### PAIR ER-02 - ValidationError cluster (five classes, no shared base)

| Name | File:Line |
|---|---|
| ResourceValidationError | core/resources/_errors.py |
| RegistryValidationError | domain/calculations/registry/ |
| InvoiceValidationError | domain/invoices/_errors.py |
| InventoryValidationError | domain/profile/errors.py |
| CliValidationBoundaryError | entrypoints/cli/_errors.py |

All express input-failed-validation with no shared root class.

Consolidation: core/errors/validation.py :: AeatValidationError(AeatError) as base.

None in AST collision list (different names) -- SEMANTIC-ONLY FIND.

---

#### PAIR ER-03 - NotFoundError cluster (three classes, no shared base)

| Name | File:Line |
|---|---|
| ResourceNotFoundError | core/resources/_errors.py |
| CalculationRevisionNotFoundError | application/modelo/_actions.py |
| CensoSnapshotNotFoundError | application/live/ |

Consolidation: core/errors/lookup.py :: AeatNotFoundError(AeatError, KeyError) as base.

NOT IN AST collision list -- SEMANTIC-ONLY FIND.

---

#### PAIR ER-04 - Conflict / already-exists errors (no shared base)

| Name | File:Line |
|---|---|
| ProfileAlreadyExistsError | domain/user_profile/_errors.py |
| BootstrapAlreadyCompleteError | application/workflow/_errors.py |

Consolidation: AeatConflictError(AeatError) as base. Confidence: LOW.

NOT IN AST collision list -- SEMANTIC-ONLY FIND.

---

### 5. Semantic Protocol Pairs

#### PAIR P-01 - SnapshotRepository[T] Protocol vs unconforming concrete repositories

| Name | File:Line | Kind |
|---|---|---|
| SnapshotRepository[TPayload] | application/live/_snapshot_base.py:86 | Generic Protocol |
| ModeloDraftRepository | domain/filing/_repository.py:22 | Concrete SecureBoundRepository subclass |
| ProfileRepository | application/user_profile/_profile_repository.py:135 | Concrete class |
| WorkflowRunRepository | application/workflow/_persistence.py:276 | Concrete class |

SnapshotRepository[T] is the only declared generic repository Protocol. The three concrete repositories
share the same save/load/list interface shape but do not formally implement the Protocol.

Consolidation: promote to core/protocols/repository.py :: Repository[T] as runtime_checkable Protocol.

NOT IN AST collision list -- SEMANTIC-ONLY FIND.

---

### 6. Cross-Reference Table - Semantic-Only Finds

Pairs found by this RAG audit that do NOT appear in any AST name-collision audit.

| Pair ID | Names | Category | Confidence |
|---|---|---|---|
| E-04 | ModeloDraftStatus / SubmissionStatus | Enum | HIGH |
| E-05 | ReconciliationStatus / ReconcileOutcome | Enum | HIGH |
| E-06 | BucketLifecycleStatus / UserProfileStatus | Enum | HIGH |
| F-01 | _hash_file x 3 copies | Function | HIGH |
| F-02 | SHA-256 bytes-to-hex one-liners x 5 | Function | HIGH |
| F-03 | _normalise_period x 2 copies in sibling subpackages | Function | HIGH |
| F-04 | validate_identity / _normalise_tax_identity | Function | MEDIUM |
| F-05 | _load_registry_snapshot / _load_snapshot / _registry_snapshot | Function | MEDIUM |
| ER-02 | ValidationError cluster (5 classes) | Error | MEDIUM |
| ER-03 | NotFoundError cluster (3 classes) | Error | MEDIUM |
| ER-04 | ProfileAlreadyExistsError / BootstrapAlreadyCompleteError | Error | LOW |
| P-01 | SnapshotRepository[T] vs concrete repository shape | Protocol | MEDIUM |

Total semantic-only pairs: 12
AST-confirmed pairs also verified by RAG: 9 (E-01 E-02 E-03 C-01 C-02 C-03 C-04 C-05 ER-01)
Delta (RAG-only finds not in any AST audit): 12

---

### 7. Index Freshness Note

- Index confirmed current at audit start (2026-05-31) via vaultspec-rag status.
- Codebase chunks: 106,932. Vault documents: 3,565.
- Device: NVIDIA RTX 4080 SUPER (16,375 MB VRAM), CUDA acceleration active.
- No parse failures reported. All Python source under src/aeat/ is covered.
- No reindex was required before running queries.
