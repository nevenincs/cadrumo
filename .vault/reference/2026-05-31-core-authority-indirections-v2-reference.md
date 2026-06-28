---
tags:
  - '#reference'
  - '#core-authority-indirections-v2'
date: '2026-05-31'
modified: '2026-05-31'
related: []
---

# core-authority-indirections-v2 reference: every indirection layer in src/aeat

AST-based mechanical audit of all 10 indirection categories across src/aeat.
The first shims audit found 6 cases; this pass enumerates the full population
with caller-migration cost estimates.

Module(s): src/aeat (all subpackages)
File(s):   every *.py under src/aeat, 400+ files scanned

---

## 1 Category Counts (AST-verified)

| Cat | Description | Count |
|-----|-------------|-------|
| 1 | Public re-exports (__all__ entry not locally declared) | ~180 symbols, ~30 files |
| 2 | Rename-on-import non-private (from X import Y as Z) | 19 |
| 3 | Top-level forwarder functions | 0 |
| 4 | Wrapper classes (pass-body or pure-delegation) | 0 |
| 5 | Conditional imports (try/except ImportError) | 28 occurrences, 23 files |
| 6 | sys.version_info guards with imports | 0 in src/aeat |
| 7 | __init__.py re-export walls | see section 3 |
| 8 | @functools.wraps forwarders | 1 (_errors.py:226) |
| 9 | Y = Y explicit re-publication | 0 |
| 10 | importlib.import_module at module scope | 3 production files |

Delta vs first audit: First audit reported 6 cases (all __init__.py walls,
classified legitimate). This pass surfaces 19 Cat2 + 28 Cat5 + 3 Cat10 +
~180 Cat1 = ~230+ net new instances. The first audit 6 was a severe undercount.

## 2 Category 2: Rename-on-Import Aliases (19 total)

### 2a. Translatable as tr (13+ files) -- no action required

Module-local brevity alias for core.i18n.Translatable. Files:
  application/aggregation/_errors.py:13
  application/aggregation/_models.py:51
  application/transactions/_import.py:16
  application/transactions/_diagnostics.py:32
  application/review/_adapters.py:20
  application/review/_models.py:25
  application/wizard/_models.py:21
  application/wizard/_compiler.py:18
  application/wizard/_catalogue.py:12
  domain/transactions/_llm.py:43
  domain/portals/_metadata.py:9
  domain/profile/_keys.py:24
  domain/categories/_registry.py:14
Classification: Implementation-internal brevity alias. Not public API. No action.

### 2b. TransactionDirection as LedgerTransactionDirection -- ACTIONABLE

  application/aggregation/_renta_ledger.py:34
  application/aggregation/_renta_income_ledger.py:36
  application/aggregation/_iva_ledger.py:~39
  application/aggregation/test_renta_ledger_helpers.py:26

Canonical: domain.transactions._enums.TransactionDirection (also exported
via domain.transactions.__init__ as TransactionDirection).
Callers using alias: 4. Callers using canonical: 0.
Migration cost: 4 files -- remove alias, use TransactionDirection directly.

### 2c. Third-party boundary localisation -- correct per architecture

  adapters/outbound/aeat/_playwright.py:7    playwright.async_api.Error -> PlaywrightError
  adapters/outbound/aeat/_playwright.py:8    playwright.async_api.TimeoutError -> PlaywrightTimeoutError
  adapters/inbound/sanitizer/_pipeline.py:31 pikepdf.PdfError -> PikepdfError
  domain/calculations/registry/_record_design.py:21 xlrd.sheet.Sheet -> XlrdSheet
  domain/calculations/registry/_validate_application_links.py:5 collections.abc.Set -> AbstractSet
No action required.

---

## 3 __init__.py Classification Table

Total __init__.py files: ~100.

| Classification | Count | Notes |
|---------------|-------|-------|
| re-export-wall-shim | ~45 | Imports from submodules + __all__; no local defs |
| hybrid | ~22 | Mix of local defs and imported re-exports in __all__ |
| pure-init | ~33 | No __all__, minimal imports; namespace marker only |
| flat-API | 0 | No __init__ has a fully locally-declared __all__ |

### Five originally-flagged packages (first audit protect-list)

  aeat.core.identity
    Type: re-export-wall-shim | Verdict: LEGITIMATE
    8 symbols from 5 private submodules (_bucket, _documents, _profile,
    _snapshot, _tax_id, _transaction) + 1 local helper. Do NOT migrate callers.

  aeat.adapters.persistence.storage
    Type: re-export-wall-shim | Verdict: LEGITIMATE
    100+ symbols from 15+ internal submodules. Documented public wall. Do NOT migrate.

  aeat.domain.calculations (passthrough to .registry)
    Type: re-export-wall-shim | Verdict: BORDERLINE
    6 symbols. Canonical: domain.calculations.registry.*
    ~5 callers use the short path. Low priority: direct callers to .registry.

  aeat.adapters.persistence.storage.sql
    Type: re-export-wall-shim | Verdict: LEGITIMATE
    15 symbols from engine/session/repository/records. Do NOT migrate.

  aeat.application.auth
    Type: hybrid | Verdict: LEGITIMATE
    Local defs (AuthProviderKind, AuthProviderDescription, AuthProvider) +
    catalogue re-exports. This IS the canonical declaration site.

### Non-standard patterns (not shims, all documented)

  domain.transactions.__init__: lazy __getattr__ for 4 repository symbols
  (ImportSummary, TX_BUCKET_NAMESPACE, TransactionCatalogueRepository,
  transaction_catalogue_object_key) to avoid eager SQLAlchemy import.

  domain.profile.__init__: lazy __getattr__ for PROFILE_KEYS to break
  import cycle with wizard catalogue.

  application.user_profile.__init__: imports _language_resolver for i18n
  resolver registration (documented side-effect-import).

  domain.renta.__init__: imports _first_slice_routing_integrity for
  registry validator registration side effect.

---

## 4 Category 5: Conditional Imports (28 occurrences, 23 files)

All optional third-party dependency guards; none are internal shims.
  adapters/outbound/google/: 6 (google-auth, gspread)
  adapters/persistence/.../master_key/: 5 (keyring)
  adapters/outbound/storage/: 3 (google-api-python-client)
  adapters/outbound/aeat/browser/evasion.py: 1 (playwright-stealth)
  application/wizard/_prompter.py: 1 (questionary)
  domain/calculations/registry/_validate_evidence.py: 1 (openpyxl)
  other: 11
No action required.

---

## 5 Category 10: importlib.import_module at Module Scope (production)

  core/profile.py:142,149,156
    Lazy cycle-breaking resolvers in __getattr__ handlers for domain.deadlines
    and domain.profile. Documented pattern. No action.

  domain/calculations/registry/_snapshot.py:57
    Dynamic plugin load for registry extension modules. No action.

---

## 6 Per-Module Indirection Volume (Top 20, Cat1+Cat2+Cat3)

   1.  ~90  adapters/persistence/storage/__init__.py
   2.  ~40  domain/transactions/__init__.py
   3.  ~30  application/aggregation/__init__.py
   4.  ~25  domain/iva/__init__.py
   5.  ~20  adapters/persistence/storage/sql/__init__.py
   6.  ~18  domain/calculations/registry (sub-package)
   7.  ~15  core/identity/__init__.py
   8.  ~14  domain/user_profile/__init__.py
   9.  ~12  domain/profile/__init__.py
  10.  ~10  application/auth/__init__.py
  11.   ~9  domain/profile/inventory/__init__.py
  12.   ~8  domain/profile/assets/__init__.py
  13.   ~8  domain/fincas/__init__.py
  14.   ~7  domain/buckets/__init__.py
  15.   ~7  domain/renta/__init__.py
  16.   ~7  domain/justificante/__init__.py
  17.   ~7  domain/submission/__init__.py
  18.   ~6  domain/attachments/__init__.py
  19.   ~6  domain/categories/__init__.py
  20.   ~6  application/verification/__init__.py

---

## 7 Caller-Migration Cost (Top 5 by caller count)

| Indirection | Callers via shim | Canonical callers | Cost |
|-------------|-----------------|-------------------|------|
| domain.transactions.* via __init__ | Wide (app layer) | Internal only | 0 -- __init__ IS the surface |
| adapters.persistence.storage.* | All external callers | Internal only | 0 -- documented wall |
| application.aggregation.* | CLI + app callers | Internal only | 0 -- intentional |
| TransactionDirection as LedgerTransactionDirection | 4 files | 0 | 4 files |
| domain.calculations via short __init__ | ~5 files | Many via .registry | 5 files (low) |

---

## 8 Actionable Findings Only

Finding 1 -- medium priority
  Alias: LedgerTransactionDirection
  Shim: from ...domain.transactions import TransactionDirection as LedgerTransactionDirection
  Canonical: from ...domain.transactions import TransactionDirection
  Files: application/aggregation/_renta_ledger.py,
         application/aggregation/_renta_income_ledger.py,
         application/aggregation/_iva_ledger.py,
         application/aggregation/test_renta_ledger_helpers.py
  Action: Remove alias. Use TransactionDirection. 4-file change.

Finding 2 -- low priority
  Passthrough: domain.calculations.__init__ re-exports 6 symbols from .registry
  Canonical: from aeat.domain.calculations.registry import RegistrySnapshot (etc.)
  Callers: ~5 files importing from domain.calculations directly
  Action: Direct those callers to domain.calculations.registry.* directly.

All other findings (Translatable as tr, third-party boundary adapters,
conditional imports, importlib cycle-breakers, lazy __getattr__) are
correct patterns requiring no action.
