---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:ec63da8ca8527fcb6240cb97ab021080f6145a08f1b3e82db1cb446a4b2a85df'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `justfile-design` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
- `S01` `M` `dev/init/__init__.py`
- `S01` `M` `dev/init/README.md`
- `S01` `M` `dev/init/__main__.py`
- `S01` `M` `dev/init/contract.py`
- `S01` `M` `dev/init/dotenv.py`
- `S01` `M` `dev/init/hooks.py`
- `S01` `M` `dev/init/plan.py`
- `S01` `verify:` `uv run --no-sync python -m compileall -q dev/env dev/init dev/quality dev/audit` -> `pass`
- `S02` `M` `dev/env/__init__.py`
- `S02` `M` `dev/env/__main__.py`
- `S02` `M` `dev/env/playwright_doctor.py`
- `S02` `verify:` `just --dry-run setup` -> `pass`
- `S02` `verify:` `just --dry-run setup-workstation-tools` -> `pass`
- `S02` `verify:` `just --dry-run setup-browser` -> `pass`
- `S03` `A` `dev/env/doctor.py`
- `S03` `A` `dev/env/tests/test_doctor.py`
- `S03` `M` `dev/env/__init__.py`
- `S03` `M` `dev/env/__main__.py`
- `S03` `verify:` `uv run --no-sync pytest --confcutdir=dev -q dev/audit/tests/test_complexity_scan.py dev/env/tests/test_doctor.py dev/quality/tests/test_suite_gate_table.py dev/audit/tests/test_advisory_report.py` -> `pass`
- `S03` `verify:` `uv run --no-sync python -m dev.env doctor` -> `pass`
- `S04` `T`
- `S04` `verify:` `just --dry-run clean; just --dry-run clean-apply` -> `pass`
- `S05` `M` `dev/quality/write_path_coverage.py`
- `S05` `verify:` `uv run --no-sync python -m dev.quality.write_path_coverage --json` -> `pass`
- `S05` `verify:` `uv run --no-sync python -m dev.audit.write_path_coverage --json` -> `pass`
- `S05` `verify:` `uv run --no-sync pytest --confcutdir=dev -n0 -m integration -q dev/tests/test_write_path_coverage_gate.py -k "not live_shipped"` -> `pass`
- `S06` `M` `dev/quality/suite.py`
- `S06` `M` `dev/quality/tests/test_suite_gate_table.py`
- `S06` `verify:` `uv run --no-sync pytest --confcutdir=dev -q dev/quality/tests/test_suite_gate_table.py dev/audit/tests/test_advisory_report.py dev/audit/tests/test_dead_code.py` -> `pass`
- `S07` `M` `dev/audit/advisory.py`
- `S07` `M` `dev/audit/complexity.py`
- `S07` `M` `dev/audit/dead_code.py`
- `S07` `M` `dev/audit/duplication.py`
- `S07` `M` `dev/audit/report.py`
- `S07` `M` `dev/audit/tests/test_complexity_scan.py`
- `S07` `M` `dev/audit/security.py`
- `S07` `M` `dev/audit/tests/test_security.py`
- `S07` `M` `dev/audit/write_path_coverage.py`
- `S07` `verify:` `uv run --no-sync pytest --confcutdir=dev -q dev/audit/tests/test_complexity_scan.py dev/audit/tests/test_advisory_report.py dev/audit/tests/test_dead_code.py` -> `pass`
- `S07` `verify:` `uv run --no-sync pytest --confcutdir=dev -n0 -q dev/audit/tests/test_security.py dev/audit/tests/test_advisory_dimensions_scan.py` -> `pass`
- `S08` `M` `dev/audit/report.py`
- `S08` `M` `dev/audit/tests/test_advisory_dimensions_scan.py`
- `S08` `verify:` `uv run --no-sync pytest --confcutdir=dev -q dev/audit/tests/test_complexity_scan.py dev/audit/tests/test_advisory_report.py` -> `pass`
- `S09` `T`
- `S09` `verify:` `uv run --no-sync pytest --confcutdir=dev -q dev/audit/tests/test_dependency_audit_gate.py` -> `pass`
- `S10` `M` `dev/registry/conformance/cli.py`
- `S10` `A` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `S10` `verify:` `uv run --no-sync pytest -q --confcutdir=dev/registry/conformance/tests dev/registry/conformance/tests/test_lifecycle_cli.py` -> `pass`
- `S11` `M` `dev/registry/conformance/cli.py`
- `S11` `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `S11` `verify:` `uv run --no-sync python -m dev.registry.conformance runtime-load --json` -> `pass`
- `S11` `verify:` `bundled_authority corrupt-artifact probe` -> `pass`
- `S12` `A` `dev/registry/analysis/registry_status.py`
- `S12` `M` `dev/registry/analysis/generated_tree_state.py`
- `S12` `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `S12` `M` `dev/registry/conformance/cli.py`
- `S12` `M` `dev/registry/pipeline/cli.py`
- `S12` `verify:` `just --dry-run report-registry-status` -> `pass`
- `S13` `M` `dev/registry/pipeline/cli.py`
- `S13` `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `S13` `M` `justfile`
- `S13` `verify:` `uv run --no-sync python -m dev.registry.pipeline --help` -> `pass`
- `S14` `M` `dev/registry/pipeline/render_check.py`
- `S14` `M` `dev/registry/pipeline/cli.py`
- `S14` `verify:` `uv run --no-sync python -m dev.registry.pipeline.render_check 296 2024-y-siguientes --check` -> `pass`
- `S15` `A` `dev/registry/validation/regulatory_literals.py`
- `S15` `D` `dev/quality/modelo_regulatory_literals.py`
- `S15` `D` `dev/registry/analysis/modelo_regulatory_literal_scan.py`
- `S15` `M` `dev/registry/tests/test_governed_literal_discovery.py`
- `S15` `M` `dev/registry/tests/test_modelo_regulatory_literal_scan.py`
- `S15` `M` `justfile`
- `S15` `verify:` `uv run --no-sync python -m dev.registry.validation.regulatory_literals` -> `pass`
- `S16` `A` `dev/registry/validation/regulatory_embeds.py`
- `S16` `D` `dev/quality/modelo_regulatory_embeds.py`
- `S16` `D` `dev/registry/analysis/modelo_embed_scan.py`
- `S16` `M` `dev/registry/tests/test_modelo_specific_embed_scan.py`
- `S16` `M` `justfile`
- `S16` `verify:` `uv run --no-sync python -m dev.registry.validation.regulatory_embeds` -> `fail`
- `S17` `M` `dev/test_runs/__main__.py`
- `S17` `M` `dev/test_runs/lanes.py`
- `S17` `A` `dev/test_runs/tests/test_lanes.py`
- `S17` `verify:` `uv run --no-sync pytest -q -n0 --confcutdir=dev/test_runs/tests dev/test_runs/tests/test_lanes.py` -> `pass`
- `S18` `M` `dev/tests/test_lane_reachability.py`
- `S18` `verify:` `uv run --no-sync pytest -q -n0 --confcutdir=dev/tests dev/tests/test_lane_reachability.py -k canonical_population` -> `pass`
- `S19` `M` `justfile`
- `S19` `M` `dev/packaging/tests/test_preflight_recipe_selection.py`
- `S19` `verify:` `just --dry-run test-packaging-preflight test-packaging-artifacts` -> `pass`
- `S20` `M` `justfile`
- `S20` `verify:` `just --dry-run test-devcontainer test-runner-image` -> `pass`
- `S21` `M` `justfile`
- `S21` `verify:` `just --dry-run setup` -> `pass`
- `S21` `verify:` `just --dry-run setup-check` -> `pass`
- `S21` `verify:` `just --dry-run doctor-dev` -> `pass`
- `S21` `verify:` `just --dry-run doctor-product` -> `pass`
- `S21` `verify:` `just --dry-run doctor-python` -> `pass`
- `S21` `verify:` `just --dry-run doctor-browser` -> `pass`
- `S22` `M` `justfile`
- `S22` `M` `dev/quality/suite.py`
- `S22` `M` `dev/quality/tests/test_suite_gate_table.py`
- `S22` `verify:` `uv run --no-sync pytest --confcutdir=dev -q dev/quality/tests/test_suite_gate_table.py` -> `pass`
- `S22` `verify:` `just --dry-run check-code` -> `pass`
- `S22` `verify:` `just --dry-run check-repository` -> `pass`
- `S23` `M` `justfile`
- `S23` `verify:` `uv run --no-sync ruff check dev/init dev/env dev/quality dev/audit dev/tests/test_write_path_coverage_gate.py` -> `pass`
- `S23` `verify:` `uv run --no-sync ruff format --check dev/init dev/env dev/quality dev/audit dev/tests/test_write_path_coverage_gate.py` -> `pass`
- `S23` `verify:` `just --dry-run fix-code` -> `pass`
- `S23` `verify:` `just --dry-run fix-style` -> `pass`
- `S23` `verify:` `just --dry-run fix-imports` -> `pass`
- `S23` `verify:` `just --dry-run fix-format` -> `pass`
- `S23` `verify:` `just --dry-run generate-corpus-text; just --dry-run generate-corpus-sidecars` -> `pass`
- `S24` `M` `justfile`
- `S24` `verify:` `just --dry-run audit-code` -> `pass`
- `S24` `verify:` `just --dry-run audit-complexity` -> `pass`
- `S24` `verify:` `just --dry-run audit-dead-code` -> `pass`
- `S24` `verify:` `just --dry-run audit-duplication` -> `pass`
- `S24` `verify:` `just --dry-run audit-code-security` -> `pass`
- `S24` `verify:` `just --dry-run check-dependency-vulnerabilities` -> `pass`
- `S24` `verify:` `just --dry-run report-code-health` -> `pass`
- `S24` `verify:` `just --dry-run report-code-health-monthly` -> `pass`
- `S25` `M` `justfile`
- `S25` `verify:` `just check-registry` -> `pass`
- `S26` `M` `justfile`
- `S26` `M` `dev/tests/test_lane_reachability.py`
- `S26` `verify:` `just --dry-run test-product test-registry test-tooling` -> `pass`
- `S27` `M` `justfile`
- `S27` `verify:` `just --dry-run test-product` -> `pass`
- `S28` `M` `justfile`
- `S28` `M` `dev/tests/test_lane_reachability.py`
- `S28` `verify:` `uv run --no-sync pytest -q -n0 --confcutdir=dev/tests dev/tests/test_lane_reachability.py -k canonical_population` -> `pass`
- `S29` `M` `justfile`
- `S29` `verify:` `git diff --check -- justfile` -> `pass`
- `S30` `M` `justfile`
- `S30` `M` `dev/packaging/tests/test_preflight_recipe_selection.py`
- `S30` `verify:` `just --dry-run build-release build-packaging-cohort build-infrastructure test-packaging-artifacts` -> `pass`
- `S31` `M` `justfile`
- `S31` `verify:` `just --dry-run locales-set es demo.key "Texto con spaces"` -> `pass`
- `S32` `M` `justfile`
- `S32` `verify:` `just --dry-run release-preview` -> `pass`
- `S33` `M` `justfile`
- `S33` `verify:` `just --dry-run clean; just --dry-run clean-apply` -> `pass`
- `S37` `M` `.github/ci-contract-allow.txt`
- `S37` `M` `.github/workflows/ci-full.yml`
- `S37` `M` `.github/workflows/ci.yml`
- `S37` `A` `.vault/audit/2026-09-14-justfile-design-pre-commit-repair-review-audit.md`
- `S37` `A` `.vault/exec/2026-09-11-justfile-design/2026-09-11-justfile-design-W05-P14-S37.md`
- `S37` `M` `.vault/index/justfile-design.index.md`
- `S37` `M` `dev/ci/tests/test_ci_workflow.py`
- `S37` `M` `dev/init/README.md`
- `S37` `M` `dev/init/__main__.py`
- `S37` `M` `dev/init/contract.py`
- `S37` `D` `dev/init/hooks.py`
- `S37` `M` `dev/quality/fixes.py`
- `S37` `M` `dev/quality/metadata/import_load_targets.json`
- `S37` `A` `dev/quality/tests/test_fixes.py`
- `S37` `A` `dev/quality/tests/test_ty_fix_boundary.py`
- `S37` `A` `dev/tests/test_precommit_policy.py`
- `S37` `M` `justfile`
- `S37` `M` `prek.toml`
- `S37` `verify:` `uv run --no-sync prek validate-config prek.toml` -> `pass`
- `S37` `verify:` `just check-workflows` -> `pass`
- `S37` `verify:` `just check-gate-contracts` -> `pass`
- `S37` `verify:` `test-ci-contracts focused normal selection` -> `pass`
- `S37` `verify:` `repair p95 performance selection` -> `pass`
- `S52` `M` `dev/init/README.md`
- `S52` `M` `dev/init/plan.py`
- `S52` `verify:` `just --dry-run setup` -> `pass`
- `S52` `verify:` `just --dry-run setup-workstation-tools` -> `pass`
- `S52` `verify:` `just --dry-run setup-browser` -> `pass`
- `S53` `M` `dev/registry/pipeline/cli.py`
- `S53` `M` `justfile`
- `S53` `verify:` `uv run --no-sync python -m dev.registry.pipeline target-current 296 2024-y-siguientes aeat-dr-296-2024 2024 0A` -> `pass`
- `S54` `A` `dev/registry/analysis/registry_status.py`
- `S54` `M` `dev/registry/analysis/generated_tree_state.py`
- `S54` `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `S54` `M` `dev/registry/pipeline/cli.py`
- `S54` `verify:` `just --dry-run report-registry-generated-state` -> `pass`
- `S55` `M` `dev/registry/pipeline/cli.py`
- `S55` `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `S55` `M` `justfile`
- `S55` `verify:` `just --dry-run registry-publish-authority` -> `pass`
- `S56` `M` `dev/registry/pipeline/cli.py`
- `S56` `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `S56` `M` `justfile`
- `S56` `verify:` `just --dry-run registry-publish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A` -> `pass`
- `S56` `verify:` `just --dry-run registry-republish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A EXPECTED_MANIFEST_SHA256` -> `pass`
- `S57` `M` `justfile`
- `S57` `M` `dev/tests/test_lane_reachability.py`
- `S57` `verify:` `uv run --no-sync pytest -q -n0 --confcutdir=dev/tests dev/tests/test_lane_reachability.py -k capability_holds_out` -> `pass`
- `S58` `M` `dev/docs/preprocess/tests/test_golden_queries.py`
- `S58` `M` `dev/tests/test_lane_reachability.py`
- `S58` `verify:` `uv run --no-sync pytest -q --collect-only -n0 --confcutdir=dev/docs/preprocess/tests -m resident_service dev/docs/preprocess/tests/test_golden_queries.py dev/docs/terminology/tests/test_sweep_live_service.py` -> `pass`
- `S59` `M` `justfile`
- `S59` `verify:` `just --list` -> `pass`
- `S59` `verify:` `just --dry-run setup` -> `pass`
- `S59` `verify:` `just --dry-run setup-check` -> `pass`
- `S59` `verify:` `just --dry-run doctor-dev` -> `pass`
- `S59` `verify:` `just --dry-run doctor-product` -> `pass`
- `S59` `verify:` `just --dry-run doctor-python` -> `pass`
- `S59` `verify:` `just --dry-run doctor-browser` -> `pass`
- `S60` `A` `dev/registry/analysis/registry_status.py`
- `S60` `M` `justfile`
- `S60` `verify:` `just --dry-run report-registry-status` -> `pass`
- `S60` `verify:` `just --dry-run report-registry-generated-state` -> `pass`
- `S61` `M` `justfile`
- `S61` `verify:` `just --dry-run registry-publish-authority` -> `pass`
- `S61` `verify:` `just --dry-run registry-publish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A` -> `pass`
- `S61` `verify:` `just --dry-run registry-republish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A EXPECTED_MANIFEST_SHA256` -> `pass`
- `S62` `M` `justfile`
- `S62` `verify:` `just --list` -> `pass`
- `S63` `M` `justfile`
- `S63` `verify:` `just --show tui-review` -> `pass`
- `S64` `M` `justfile`
- `S64` `verify:` `just --dry-run db-migration-create "synthetic local check"` -> `pass`
- `S78` `M` `justfile`
- `S78` `M` `dev/test_runs/__main__.py`
- `S78` `M` `dev/test_runs/command.py`
- `S78` `M` `dev/test_runs/lanes.py`
- `S78` `M` `dev/test_runs/tests/test_command.py`
- `S78` `M` `dev/test_runs/tests/test_lanes.py`
- `S78` `verify:` `uv run --no-sync pytest -q -n0 dev/test_runs/tests/test_command.py dev/test_runs/tests/test_lanes.py` -> `pass`
- `S78` `verify:` `uv run --no-sync pytest -q -n0 dev/tests/test_lane_reachability.py::<four registry ownership checks>` -> `pass`
- `S78` `verify:` `uv run --no-sync ruff check dev/test_runs` -> `pass`
- `S78` `verify:` `just --show test-registry` -> `pass`
- `S78` `verify:` `just test-registry` -> `fail`

## Notes

- `S04` No source mutation was required; the existing clean implementation already isolates reporting from setup and diagnosis.
- `S09` The existing dependency-audit implementation already owned the blocking finding and unavailable-data exit contract; the public canonical check invokes it directly without duplicating analysis.
- `S12` Live status reports 95 generated targets as unreadable because the canonical owner could not re-render them; exclusions remain fail-visible.
- `S16` The relocated validator reproduces 22 pre-existing findings.
- `S22` `check-workflows` uses the existing `dev/actionlint.py` provisioner, which can write a cached executable when `actionlint` is absent; the read-only correction remains an integration dependency outside this lane's owned Python surfaces.
- `S37` The full `test-ci-contracts` aggregate remains red from concurrent product,
- `S37` fixture, generated-data, and secure-storage changes outside S37; the focused
- `S37` blocking selection owned by this step passes. Declared-lane reachability still
- `S37` reports two unrelated product tests and no longer reports the repair benchmark.
- `S58` Resident-service tests remain outside public population accounting for W05's
- `S58` RAG recipe removal; the pure workbook-classification test is reclassified into
- `S58` repository contracts.
- `S62` The legacy generic wrappers remain until W05 completes repository-wide caller migration and removal.
- `S63` `uv run --no-sync python -m dev.tui.harness --help` -> `fail` (pre-existing import mismatch; no harness started)
- `S64` `uv run --no-sync alembic --help` -> `fail` (pre-existing missing Alembic command; no database upgrade executed)
- `S78` The live registry remains unloadable during the concurrent refactor: collection currently raises `PydanticSchemaGenerationError` for `Modelo`, and artifact-backed loading raises it for `TaxDomain`. The improved signal reports those as collection and load preflight failures and blocks all granular lanes.
- `S78` No commit was created because another active process holds the shared worktree's Git index lock. No unrelated changes were staged or altered.
