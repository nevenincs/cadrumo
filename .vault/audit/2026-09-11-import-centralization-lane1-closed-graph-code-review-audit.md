---
tags:
  - '#audit'
  - '#import-centralization'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:f309289b292d06cf8997c55154b6d2e675988307e3ee0260807ccdc7eb8bc334'
related:
  - "[[2026-09-11-import-centralization-import-authority-drift-audit]]"
  - "[[2026-07-01-import-centralization-adr]]"
  - "[[2026-07-02-arch-remediation-ports-inversion-adr]]"
  - "[[2026-07-08-importlinter-test-carveout-adr]]"
  - "[[2026-07-01-import-centralization-plan]]"
---
# `import-centralization` audit: `Lane 1 closed graph code review`

## Scope

Reviewed the closed Import Linter configuration, the inward core/domain/application changes, the inert shared test namespace, the domain-owned resource relocation, the registry-test helper relocation, and the focused verification evidence for Steps `W07.P91.S404-S407` and `W07.P92.S408-S411`. Static imports include module-level, `TYPE_CHECKING`, and function-local imports. No exception, baseline, warning-only contract, wildcard carve-out, or import suppression was added.

## Findings

### Lane 1 closed graph code review | high | Application production still reaches concrete adapters

The authoritative graph still reports the application contract broken. The AST census finds 338 direct production occurrences from `cadrumo.application` to `cadrumo.adapters`, including `cadrumo.application.aggregation._impatriado_income_ledger` to `cadrumo.adapters.persistence.profile.transactions`, `cadrumo.application.filing.persistence_wiring` to `cadrumo.adapters.persistence.profile.modelos_filing`, `cadrumo.application.ledger.actions_import` to the financial-provider adapters, `cadrumo.application.live.filed_data_capture` to AEAT declaration adapters, and `cadrumo.application.storage.calc_sheets.parity_harness` to the Google Sheets adapter. These require inward ports and entrypoint composition, so they are a Lane 2 handoff.

### Lane 1 closed graph code review | high | Source test cohorts still use repository-only authoring support

The shipped-code contract still reports source tests reaching `test_support` and, transitively, `dev`. The exact direct census is 213 domain-test occurrences, 20 application-test occurrences, and one `cadrumo.tests.registry_snapshot` occurrence. Examples are `cadrumo.domain.calculations.registry.tests.test_modelo_100_registry` to `test_support.registry_authoring`, `cadrumo.application.filing.tests.test_modelo_347_contraparte_export_parity` to `test_support.registry_authoring`, and `cadrumo.tests.registry_snapshot:13` to `test_support.registry_authoring`. These authoring/oracle cohorts belong in the development test seam and require Lane 3 relocation; replacing them with a source-side duplicate would violate the no-compatibility/no-duplication boundary.

### Lane 1 closed graph code review | high | Shared `cadrumo.tests` is not yet core-only

The shared-test contract still reports 206 direct non-core occurrences: 78 to domain, 46 to application, 78 to adapters, three to entrypoints, and one to `test_support`. Representative importers are `cadrumo.tests.test_secure_sql`, `cadrumo.tests.cli_runner`, and `cadrumo.tests.registry_snapshot`. The package initializer itself is now inert and the remaining helpers must be split or moved to their nearest outer seam by the owning lanes.

### Lane 1 closed graph code review | medium | Cross-layer tests remain at the inward location

Core tests still have 20 adapter, eight application, and 18 domain occurrences; domain tests still have 75 adapter and 26 application occurrences. Application tests still have 1,233 adapter, ten entrypoint, and 20 repository-support occurrences. Tests such as `cadrumo.application.overview.tests.test_calendar_model_ownership` import `RemoteNotification` from an adapter and assert package-facade exports, so they need an outer seam rather than a narrower exemption. Adapter/entrypoint moves are Lane 2 handoffs.

### Lane 1 closed graph code review | medium | Relocated resource cohort has retired-topic and registry hashability blockers

The moved resource tests collect 44 tests; the focused run passes 42. `cadrumo.domain.resources.tests.test_registry` still expects the retired `topics` repository, and `cadrumo.domain.resources._repos.tests.test_year_keyed` reaches `domain.deadlines.festivos` and fails because `ValidatedRegistryAuthority` is unhashable. The retired repository must not be restored; the hashability failure belongs to the existing domain implementation owner.

### Lane 1 closed graph code review | low | Repository-wide type inventory remains red outside the changed contracts

`just check-types` reports 786 diagnostics (734 ty, two pyrefly, 50 basedpyright), dominated by existing domain/dev files. All self-contained changed production files pass targeted `basedpyright` (0 errors) and `pyrefly` (0 errors; warnings not shown). Whole-owned Ruff reports only ten pre-existing docstring errors in clean registry files; all 178 changed Python files pass targeted Ruff and formatting.

## Recommendations

- Lane 2 should move the concrete construction and adapter-facing contracts from the exact application producer families above into inward application/domain ports, then compose implementations in entrypoints.
- Lane 3 should relocate registry-authoring/oracle cohorts and split `test_support` so source tests do not import repository-only support; preserve assertions at the development or outer seam.
- The resource `topics` test should be retired or reconciled with the already-retired production repository, and the `festivos` owner should fix the hashability defect. Neither issue justifies an Import Linter exemption.
- Keep the closed Import Linter contracts authoritative and keep all forbidden edges visible until the handoffs land.
### Lane 1 closed graph code review | high | Review confirms the registry-authoring seam is not closed

The independent read-only review confirms that `src/cadrumo/domain/calculations/registry/tests/_scenarios.py:17` still reaches `test_support.registry_authoring`, which in turn imports private `dev.registry.compiler` helpers. Broad collection also reaches the same repository-only surface through `src/cadrumo/conftest.py:311`. This is a direct S407/S408 failure, not a permissible test carve-out; the registry-authoring cohort must move to the development test seam under Lane 3.

### Lane 1 closed graph code review | high | Shared CLI/TUI helper seams remain outside Lane 1

The review also confirms `src/cadrumo/tests/cli_runner.py:37` and `src/cadrumo/tests/cli_performance.py:753,771` reach `cadrumo.entrypoints.cli`, while TUI tests reach `test_support.tui_*` and then `dev.tui.harness.*`. These are outer test seams for the corresponding CLI/TUI and tooling owners; no source-side compatibility helper is appropriate.
