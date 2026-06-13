---
tags:
  - '#audit'
  - '#registry-test-decomposition'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# `registry-test-decomposition` audit: `oversized registry test module decomposition audit`

## Scope

Audited oversized test modules under
`src/aeat/domain/calculations/registry` as the final P04 monolith target
before returning to registry data fragmentation follow-ups.

## Findings

### High

- The registry test package currently has 140 test modules and 39,487
  working-tree lines. The largest file is 1,565 lines and 20 test modules
  are at or above 500 lines.
- Active peer WIP exists in `test_cross_dependency_calculations.py` and
  `test_modelo_202_registry.py`. This slice must not edit test modules.
- The largest modules mix multiple behavior families. Splitting should be
  by tested contract, not by arbitrary line ranges, and must preserve real
  registry behavior. Do not introduce mocks, fakes, monkeypatches, skips,
  or tautological helper logic as a shortcut.

### Oversized Files

- `test_registry_schema.py`: 1,565 lines. Mixes schema model parsing,
  committed snapshot smoke tests, validator rejection cases, extraction
  targets, continuity metadata, export-field validation, verification
  predicates, deadline windows, keyed brackets, and convenio rates.
- `test_referential_integrity.py`: 1,386 lines. Mixes committed-registry
  integrity, dangling-reference variants, text-casilla strategy checks,
  informative-modelo invariants, segment identity, and completeness
  manifest gates.
- `test_loader_directory_mode.py`: 1,066 lines. Mixes single-file versus
  directory equivalence, fragment merge behavior, fragment rejection
  cases, stale sibling checks, reviewability size gates, and source
  inventory checks.
- `test_modelo_349_registry.py`: 974 lines. Mixes catalogues, schedules,
  authenticated read surfaces, record design, workbook parity, export
  layout, extraction profiles, invoice scalar bindings, row bindings, and
  full invoice-to-casilla pipeline.
- `test_modelo_100_registry.py`: 965 lines. Mixes revision/source
  foundation, construct membership, dependency classifications, profile
  bindings, application links, XML dictionary layout, record-design
  export path checks, validator rejection tests, and live cross-reference
  checks.
- `test_record_design.py`: 915 lines. Mixes workbook parsing, generated
  PDF parsing, committed PDF corpus parsing, completeness manifest gates,
  Diseño coverage, dispatcher/public-import discipline, and Modelo 131
  registry binding coverage.
- `test_cross_revision_drift.py`: 876 lines. Mixes synthetic
  cross-revision validator cases, committed-corpus acceptance, M100
  continuity surfaces, backend drift gate, and singleton semantic-role
  warning counts.
- `test_cross_dependency_calculations.py`: 796 lines with active peer WIP.
  Mixes cross-model relation resolution across M180/M190/M193/M100/M130,
  Modelo 202 relation selection, and M200 aggregation from M202.

### Decomposition Order

- First target: `test_loader_directory_mode.py`. It is large, has clear
  clusters, and directly supports the registry fragmentation campaign.
  Split into directory equivalence, fragment merge behavior, fragment
  rejection behavior, committed registry layout gates, and TOML
  reviewability gates.
- Second target: `test_registry_schema.py`. Split into schema model
  parsing, validator reference/link rejection cases, extraction/profile
  rules, export rules, continuity rules, verification predicates,
  deadlines, and parameter table parsing.
- Third target: `test_referential_integrity.py`. Split into committed
  integrity smoke, dangling reference categories, text-casilla strategy,
  segmented casilla identity, completeness manifest gates, and
  informative-modelo invariants.
- Fourth target: modelo-specific test files, beginning with
  `test_modelo_349_registry.py` and `test_modelo_100_registry.py`,
  because each can split by registry surface while preserving a shared
  committed-modelo fixture.
- Defer `test_cross_dependency_calculations.py` until peer WIP lands.
  It currently has active edits for Modelo 202 relation/binding coverage.

## Recommendations

1. Add decomposition steps after P04 or create a follow-up plan phase for
   oversized test modules. Each step should split one source test module
   by behavior family and commit explicit paths.
2. Keep tests real-behavior only. Do not add fakes, stubs, mocks,
   monkeypatches, skips, xfails, or mirrored business logic.
3. Prefer preserving existing helper functions in the first split. Move
   helpers to a shared test-support module only when two or more new test
   files need the same helper and the helper does not encode assertions.
4. Each split commit must run the exact source module's test set before
   and the new split modules after, plus `test_public_api_boundaries.py`
   when imports change.
5. For `test_loader_directory_mode.py`, preserve the TOML size and stale
   sibling reviewability gates as a clearly named reviewability test file,
   not as incidental loader behavior.
6. For modelo-specific splits, keep filenames grouped by public registry
   surface, for example schedule, export layout, extraction profile,
   bindings, construct coverage, and live/read-only surfaces.

## Codification candidates

- **Source:** finding High-3.
  **Rule slug:** `registry-test-decomposition-real-behavior`.
  **Rule:** Oversized registry test modules must be split by tested
  contract while preserving real registry behavior and without fakes,
  mocks, stubs, skips, xfails, monkeypatches, or mirrored business logic.
