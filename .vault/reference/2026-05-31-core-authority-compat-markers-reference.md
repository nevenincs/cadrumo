---
tags:
  - '#reference'
  - '#core-authority-compat-markers'
date: '2026-05-31'
modified: '2026-05-31'
related: []
---

# Core authority compatibility and deprecation markers

Textual scan of src/aeat/ for comments, docstrings, and naming patterns indicating deprecated, legacy, historical, back-compat, or transitional code not caught by direct codebase review.

## Marker Inventory Summary

**Total markers found:** 495 (across all categories)
**Try/except ImportError shim patterns:** 4 files
**Heavy deprecation markers:** 2
**Light explanatory markers:** ~180
**Shim-residue candidates:** ~25

## Findings

### 1. Shim-Residue Cluster: Active Compatibility Code

**_legacy_iva_wallet_decision_key function**
- Location: src/aeat/application/calculations/_observations_repository.py:139
- Private function implementing legacy key format fallback for observation caching
- Called from load_decision at line 269 as fallback path
- Test: test_load_decision_falls_back_to_legacy_cleartext_key
- Status: Bridge for pre-hardening data; removal timeline needs tracking

**BUCKET_DEK_V1 vs LEGACY_MASTER_KEY schedule**
- Location: src/aeat/adapters/persistence/storage/master_key/_master_key.py:1255-1257
- Two-path decision tolerating buckets without separated DEK documents
- Used in test: test_registered_legacy_bucket_without_dek_keeps_master_key_data_path
- Status: Architectural backward compatibility; intentional

**models.reset() manifest backfill**
- Location: src/aeat/application/workflow/_profile_health.py:242
- Backfills legacy active-bucket manifest status from encrypted record
- Status: Migration code (one-way), not dual-path shim

### 2. Genuine Deprecation Markers

docs/conf.py:45
- Legacy narrative docs scheduled for removal (heavy dev-process)

_MODELO_123_2023_LEGACY_CASILLAS fixtures
- Location: src/aeat/tests/fixtures/justificantes/_generate.py:1086-1098
- Historical form revision (2019-2023) with 8 casillas marked -legacy suffix
- Status: Versioned registry support, not a shim

### 3. Light Markers: Explanatory References

These do NOT indicate shim code:

- **historical_metadata, historical_suppression** in registry (~18 matches)
  - Domain-level enumerations for census models (modelo 037 historical-only)

- **legal references preserved for historical records** (src/aeat/domain/submission/_models.py:25-47)
  - Documents audit record provenance, not a compat path

- **legacy short-label profile identity** (src/aeat/core/identity/_profile.py:15, 35)
  - Permissive constraint accepting UUIDv4 OR legacy label

- **legacy_www external constant** (src/aeat/core/external_constants.py)
  - Old AEAT domain reference; single read-only field

### 4. Try/Except ImportError Patterns

Four files with conditional imports:
1. src/aeat/test_w05_p24_exceptions.py
2. src/aeat/application/review/_adapters.py
3. src/aeat/adapters/outbound/google/test_api.py
4. src/aeat/tests/test_cross_module_imports_resolve.py

All are test-infrastructure or intentional optional integrations; none are production shims.

### 5. Top Files by Marker Density

1. src/aeat/tests/fixtures/justificantes/_generate.py (35 markers)
2. src/aeat/domain/calculations/registry/_censo_modelos.py (28 markers)
3. src/aeat/application/calculations/test_observations_repository.py (22 markers)
4. src/aeat/domain/calculations/registry/_schema.py (18 markers)
5. src/aeat/adapters/persistence/storage/master_key/_master_key.py (14 markers)

## Recommendation

No immediate breaking changes required. The _legacy_iva_wallet_decision_key fallback warrants explicit timeline tracking. All other markers represent intentional architecture decisions, versioned fixture support, or explanatory comments.

