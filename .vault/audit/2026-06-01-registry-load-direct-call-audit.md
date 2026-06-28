---
tags:
  - '#audit'
  - '#registry-load-direct-call'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-06-01-test-suite-performance-audit]]"
  - "[[2026-05-28-codebase-solidification-plan]]"
---



# `registry-load-direct-call` audit: inventory of direct `ValidatedRegistryAuthority.load()` call sites for fixture consolidation

## Scope

Direct `ValidatedRegistryAuthority.load(registry_root, source_root)` call sites in test files fall into three operational classes:

1. **NEGATIVE-PATH**: Test mutates the `tmp_path` registry tree (manifest or revision files) before calling `.load()` to verify error handling, cache invalidation, or schema mismatch detection. These sites must retain direct `.load()` calls because the mutation semantics are essential to the test's contract.

2. **CONVENIENCE**: Test calls `.load()` on an immutable bundled registry (under `tests/fixtures/registry/`) without mutation. The call is a one-off convenience for accessing registry data (snapshots, catalogues, casilla definitions). These sites are candidates for migration to `bundled_authority()` helper or a session-scoped `registry_authority` fixture.

3. **AMBIGUOUS**: Context unclear from surrounding code; requires executor review to classify.

This audit is a precursor to cluster-5 of the test-suite-performance audit: **~250+ tests recompile registry snapshots**. Consolidating CONVENIENCE sites onto a shared fixture reduces per-test registry compilation cost by eliminating redundant snapshot rebuilds.

## Findings

**Inventory: 9 direct `.load()` call sites identified across 7 test modules.**

| File | Line | Classification | Test Context |
|------|------|---|---|
| `src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py` | 97 | CONVENIENCE | loads bundled registry, calls `.snapshot()` to access modelos |
| `src/aeat/application/overview/test_applicability.py` | 868 | CONVENIENCE | loads bundled registry, accesses `catalogues.legal` for filing regime metadata |
| `src/aeat/domain/calculations/registry/test_authority.py` | 67 | CONVENIENCE | loads bundled registry, `.snapshot()` call for model access |
| `src/aeat/domain/calculations/registry/test_authority.py` | 185 | NEGATIVE-PATH | mutates `tmp_path` manifest/revision files before load, tests cache invalidation on file changes |
| `src/aeat/domain/calculations/registry/test_authority.py` | 187 | NEGATIVE-PATH | verifies cache miss after revision is modified between two consecutive `.load()` calls |
| `src/aeat/application/filing/test_init.py` | 27 | CONVENIENCE | in `_authority()` helper function, bundled registry, used by multiple test methods |
| `src/aeat/domain/calculations/registry/test_modelo_applicability.py` | 59 | CONVENIENCE | loads bundled registry, accesses `catalogues.legal` |
| `src/aeat/domain/calculations/registry/test_queries.py` | 20 | CONVENIENCE | in `_service()` helper function, bundled registry, inlined fixture used across multiple test methods |
| `src/aeat/domain/calculations/registry/test_queries.py` | 53 | CONVENIENCE | intra-test `.load()` call, bundled registry |

**Breakdown:**
- **CONVENIENCE**: 7 sites (78%) — candidates for fixture consolidation
- **NEGATIVE-PATH**: 2 sites (22%) — must retain direct `.load()` calls
- **AMBIGUOUS**: 0 sites

## Recommendations

### Primary: Consolidate CONVENIENCE sites onto bundled_authority()

All 7 CONVENIENCE sites call `.load()` on the immutable bundled registry without mutation. Migrate these to either:

1. **`bundled_authority()` convenience function** (if available in the fixture suite), or
2. **Session-scoped `registry_authority` fixture** (if session scope is permitted by test structure)

This eliminates 7 redundant snapshot compilations per test session.

### Migration priority (by impact):

1. **`test_queries.py` (2 sites, line 20 + 53)**: Helper function `_service()` + intra-test call. Consolidation yields highest impact (multiple test methods reuse `_service()`).
2. **`test_init.py` (1 site, line 27)**: `_authority()` helper used by multiple tests; single consolidation blocks all callers.
3. **`test_modelo_applicability.py` (1 site, line 59)**: Standalone `.load()` call in test method.
4. **`test_applicability.py` (1 site, line 868)**: Standalone `.load()` call in test method.
5. **`test_calc_sheets_pull_typing.py` (1 site, line 97)**: Standalone `.load()` call in test method.

### Preserve NEGATIVE-PATH sites

The two test sites in `test_authority.py` (lines 185 and 187) verify cache invalidation and must retain direct `.load()` calls. Document their purpose in-code (if not already done) to prevent future consolidation attempts.

## Follow-up

After migration, re-measure test-suite duration (cluster-5 empirical tables in test-suite-performance audit) to quantify snapshot-rebuild cost reduction.

## Findings


