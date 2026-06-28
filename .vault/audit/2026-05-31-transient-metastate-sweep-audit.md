---
tags:
  - "#audit"
  - "#transient-metastate-sweep"
date: "2026-05-31"
modified: '2026-05-31'
related: []
---

# transient-metastate-sweep audit: embedded development metastate in production code

## Scope

Read-only sweep of src/aeat/ for every class of transient development metastate embedded
in production and test surface: allowlists/burndown lists encoding migration state,
process-citation comments, Wave/Phase/Step-encoded filenames, pending-enrollment deferrals,
and diagnostic protect-lists. Triggered by MIGRATED_COMMANDS pattern flagged by the user.

---

## 1. Headline counts by category

| Category | Symbol count | Finding count |
|---|---|---|
| Migration allowlists (burndown ledgers) | 83 entries (MIGRATED_COMMANDS) | 1 |
| Diagnostic protect-lists | 52 entries (PROMOTE001_PROTECT_LIST) | 1 |
| Pending-enrollment deferrals | 173 entries across 4 lists | 4 |
| Campaign-keyed locale key sets | 33 entries (_W04_P19_KEYS) | 1 |
| Wave/Phase/Step citations in comments | 275 lines across 97 files | 97 |
| Wave/Phase/Step-encoded test filenames | 19 files | 19 |
| Migration-state variable names | 4 sites | 4 |
| On-disk format version markers (borderline) | 2 symbols | 2 |

**Total distinct findings: 129 code locations; 5 top-concern clusters.**

TRUE-METASTATE count: 6 clusters.
LEGITIMATE-CONSTRAINT count: 4.
BORDERLINE: 4 symbols requiring human adjudication.

---

## 2. Per-finding table

### A -- Migration allowlists

| File:line | Symbol | Entries | Classification | Remediation |
|---|---|---|---|---|
| src/aeat/entrypoints/cli/test_json_schema_conformance.py:67 | MIGRATED_COMMANDS | 83 | TRUE-METASTATE | Replace with registry-driven exhaustive assertion over SCHEMA_REGISTRY.keys() vs Typer command tree. No allowlist. |

### B -- Diagnostic protect-lists

| File:line | Symbol | Entries | Classification | Remediation |
|---|---|---|---|---|
| src/aeat/diagnostics/_identity_placement.py:414 | PROMOTE001_PROTECT_LIST | 52 | BORDERLINE | HEX64/MINLEN/PATTERN entries are LEGITIMATE-CONSTRAINT; TRANSIT entries awaiting type promotion are TRUE-METASTATE. Split into _PERMANENT_CONSTRAINT_EXEMPTIONS and _TYPE_PROMOTION_DEFERRALS. |

### C -- Pending-enrollment deferrals

| File:line | Symbol | Entries | Classification | Remediation |
|---|---|---|---|---|
| src/aeat/test_clock_enrollment_inventory.py:79 | PENDING_ENROLLMENT | 81 | TRUE-METASTATE | Complete clock-call enrollment across 81 sites; delete list; harden gate. |
| src/aeat/test_decimal_enrollment_inventory.py:55 | DECIMAL_STR_PENDING | 11 | TRUE-METASTATE | Complete Decimal coerce enrollment; delete list. |
| src/aeat/test_locale_tr_positional_inventory.py:123 | _SWEPT_MODULES | 14 | TRUE-METASTATE | Inverted opt-in gate -- unswept modules silently exempt. Convert to all-module gate; delete opt-in list. |
| src/aeat/test_coverage_inventory.py:58 | COVERAGE_GAPS | 67 | TRUE-METASTATE | Close coverage gaps; delete list. Permanently untestable entries need per-entry domain rationale. |

### D -- Campaign-keyed locale key set

| File:line | Symbol | Entries | Classification | Remediation |
|---|---|---|---|---|
| src/aeat/test_locale_coverage_inventory.py:25 | _W04_P19_KEYS | 33 | TRUE-METASTATE | Symbol encodes campaign phase. Rename to _OPERATOR_ERROR_LOCALE_KEYS. |

### E -- Wave/Phase-encoded test filenames (19 files, all TRUE-METASTATE)

test_w04_p22_cleanup.py, test_w05_p23_locale_coverage.py, test_w05_p24_exceptions.py,
test_w06_p28_exceptions.py, test_w06_p29_constants_inventory.py, test_w07_p32_exceptions.py,
test_w07_p33_cleanup.py, test_w08_p34_latin1_inventory.py, test_w08_p35_exceptions.py,
test_w08_p36_dedup.py, test_w09_p37_inventory.py, test_w09_p38_rationale_inventory.py,
test_w09_p39_locale_pydantic.py, test_w10_p40_constants_inventory.py,
test_w10_p41_rationale_inventory.py, test_w11_p42_utf8_regression_proof.py,
test_w11_p43_axis_finishers.py, test_w12_p44_finishers.py, test_w13_p45_closure.py.

Rename each to describe the domain invariant asserted, not the campaign that created it.
Example: test_w08_p35_exceptions.py -> test_exception_clause_narrowing.py.

### F -- Process-citation comments (TRUE-METASTATE)

275 comment lines across 97 files citing Wave.Phase/Step coordinates,
linkage-design-audit, json-envelope-migration, etc.

Top 5 files by citation density:

| File | Citation lines |
|---|---|
| src/aeat/test_w05_p23_locale_coverage.py | 13 |
| src/aeat/entrypoints/cli/test_json_schema_conformance.py | 12 |
| src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py | 11 |
| src/aeat/test_locale_coverage_inventory.py | 9 |
| src/aeat/test_w07_p32_exceptions.py | 9 |

Delete or replace with domain rationale. Comments recording plan coordinates carry no
persistent value once a campaign closes.

### G -- Migration-state variable names

| File:line | Symbol | Classification | Note |
|---|---|---|---|
| src/aeat/core/test_aggregation.py:128 | _OLD_ABSOLUTE, _OLD_RELATIVE_MODULE | BORDERLINE | Migration guard asserting no importer of a relocated module remains. Test is correct; names encode past state. Rename to _RELOCATED_* once guard is permanent. |
| src/aeat/adapters/persistence/storage/bucket/_manifest.py:95 | BucketKeySchedule.LEGACY_MASTER_KEY | LEGITIMATE-CONSTRAINT | On-disk serialized enum value stored in existing bucket manifests. Cannot rename without data migration. |
| src/aeat/adapters/persistence/storage/_namespace_registry.py | SECURE_OBJECT_SCHEMA_VERSION_V1 | LEGITIMATE-CONSTRAINT | API schema version constant. _V1 marks an API version, not a migration window. |
| src/aeat/domain/calculations/registry/_aeat_hosts.py:7 | _AEAT_LEGACY_HOST_SUFFIX | LEGITIMATE-CONSTRAINT | Real historical AEAT hostname suffix aeat.es -- live for backwards compatibility. |
| src/aeat/tests/fixtures/justificantes/_generate.py:1086 | _MODELO_123_2023_LEGACY_CASILLAS | LEGITIMATE-CONSTRAINT | AEAT form revision identifier; casilla IDs carry -legacy suffix in the AEAT PDF itself. |
| src/aeat/adapters/inbound/declaracion/test_verification_chain.py:691 | _M303_NEW_TEMPLATE_PARAMS | BORDERLINE | Contrasts with pre-Orden-HAC/819/2024 template. Rename to _M303_2023_ONWARDS_PARAMS. |
| src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py:70 | _LEGACY_DEFAULT_REPOSITORY_EXCEPTIONS | BORDERLINE | Currently empty frozenset with anti-tautology guard. Harmless while empty. Rename to _ISOLATION_EXCEPTIONS if ever populated. |

---

## 3. Top 10 worst offenders by entry count

| Rank | Symbol | File | Entry count | Category |
|---|---|---|---|---|
| 1 | MIGRATED_COMMANDS | test_json_schema_conformance.py | 83 | Migration allowlist |
| 2 | PENDING_ENROLLMENT | test_clock_enrollment_inventory.py | 81 | Pending-enrollment deferral |
| 3 | COVERAGE_GAPS | test_coverage_inventory.py | 67 | Pending-enrollment deferral |
| 4 | PROMOTE001_PROTECT_LIST | diagnostics/_identity_placement.py | 52 | Diagnostic protect-list (borderline) |
| 5 | _W04_P19_KEYS | test_locale_coverage_inventory.py | 33 | Campaign-keyed key set |
| 6 | process-citation comments | 97 files | 275 lines | Process citations |
| 7 | Wave/Phase-encoded filenames | src/aeat/ root | 19 files | Filename metastate |
| 8 | _SWEPT_MODULES | test_locale_tr_positional_inventory.py | 14 | Pending-enrollment deferral |
| 9 | DECIMAL_STR_PENDING | test_decimal_enrollment_inventory.py | 11 | Pending-enrollment deferral |
| 10 | _OLD_ABSOLUTE/_OLD_RELATIVE_MODULE | core/test_aggregation.py | 2 | Migration-state variable names |

---

## 4. Remediation pattern catalogue

**MIGRATED_COMMANDS pattern:** Replace burndown ledger with registry-driven exhaustive assertion.
Walk the Typer app tree to discover all CLI command paths. Assert SCHEMA_REGISTRY.keys() equals
that set. Every registered command must emit an envelope -- no partial allowlist.

**Pending-enrollment deferrals:** Complete enrollment, convert test to unconditional
zero-tolerance, delete the list. Until enrollment is complete, rename the set to describe
the domain invariant (_DEFERRED_CLOCK_SITES, _DEFERRED_COERCE_SITES). Each entry must carry
a domain rationale comment, not a step reference.

**Campaign-keyed symbol names and test filenames:** Pure rename. Name after domain invariant.
_W04_P19_KEYS -> _OPERATOR_ERROR_LOCALE_KEYS. test_w08_p35_exceptions.py ->
test_exception_clause_narrowing.py. No logic changes required.

**Process-citation comments:** Delete or replace with domain rationale. Comments recording
campaign coordinates carry no persistent value. The invariant they guard should be self-describing.

**Diagnostic protect-list with mixed rationale:** Split PROMOTE001_PROTECT_LIST into
_PERMANENT_CONSTRAINT_EXEMPTIONS (domain-shape mismatch) and _TYPE_PROMOTION_DEFERRALS
(incremental deferrals; drive to empty then delete). Every permanent entry retains its rationale code.

---

## 5. Risk-ordered remediation sequence

| Priority | Category | Rationale |
|---|---|---|
| 1 | MIGRATED_COMMANDS (83 entries) | Original trigger. Largest migration ledger. Registry-driven replacement tractable now. |
| 2 | Wave/Phase-encoded test filenames (19 files) | Pure rename; zero logic change; unblocks future grep audits from false positives. |
| 3 | Process-citation comments (275 lines, 97 files) | Mechanical deletion; no logic change; eliminates largest surface area of metastate. |
| 4 | _W04_P19_KEYS rename | One symbol rename and docstring update; zero logic change. |
| 5 | PROMOTE001_PROTECT_LIST split (52 entries) | Per-entry human adjudication to separate domain-permanent from migration-deferral. |
| 6 | COVERAGE_GAPS (67 entries) | Close gaps or rename with permanent domain rationale per entry. |
| 7 | PENDING_ENROLLMENT (81 sites) | Complete clock-call enrollment; highest effort. |
| 8 | _SWEPT_MODULES (14 entries) | Convert to all-module gate once remaining modules are swept. |
| 9 | DECIMAL_STR_PENDING (11 entries) | Smallest deferral list; tractable in a single focused pass. |
| 10 | Borderline variable names | Rename after guarded invariants become permanent. Low urgency. |

Estimated atomic steps: 18-24 across 3-4 sequenced passes. Items 1-4 are rename/delete work
completable in 4-6 steps. Items 5-9 require enrollment completion; 10-80 site edits each
plus one list deletion on completion.
