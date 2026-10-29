---
tags:
  - '#exec'
  - '#gate-findings-repair'
date: '2026-10-29'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:02eecf3f478995be7986fe5f4be3c8d132771445cc813d6f813027717fe9e031'
related:
  - "[[2026-10-29-gate-findings-repair-plan]]"
---

# `gate-findings-repair` ledger

## Changes

- `S02` `M` `.importlinter`
- `S02` `M` `conftest.py`
- `S02` `M` `dev/_paths.py`
- `S02` `M` `dev/audit/security.py`
- `S02` `M` `dev/ci/logging_benchmark.py`
- `S02` `M` `dev/deploy/docs_delivery_activation.py`
- `S02` `M` `dev/deploy/docs_site_build.py`
- `S02` `M` `dev/desktop_agent_live/lane.py`
- `S02` `M` `dev/docs/build.py`
- `S02` `M` `dev/docs/cli_reference.py`
- `S02` `M` `dev/docs/cli_tree.py`
- `S02` `M` `dev/docs/i18n.py`
- `S02` `M` `dev/docs/sequences/checks.py`
- `S02` `M` `dev/docs/sequences/runner.py`
- `S02` `M` `dev/docs/sequences/sandbox.py`
- `S02` `M` `dev/docs/serve.py`
- `S02` `M` `dev/docs/serve_languages.py`
- `S02` `M` `dev/env/_venv.py`
- `S02` `M` `dev/env/browser_archive_pins.py`
- `S02` `M` `dev/locales/signal_documentation_inventory.py`
- `S02` `M` `dev/packaging/native/provider_icon_assets.py`
- `S02` `M` `dev/packaging/release_cohort_support.py`
- `S02` `M` `dev/packaging/runtime_wheelhouse.py`
- `S02` `M` `dev/quality/import_gate.py`
- `S02` `M` `dev/quality/import_load_probe.py`
- `S02` `M` `dev/registry/analysis/load_census.py`
- `S02` `M` `dev/registry/filing_export_conformance.py`
- `S02` `M` `dev/registry/parity/workbook_parity_libreoffice.py`
- `S02` `M` `dev/registry/pipeline/candidate_compile_process.py`
- `S02` `M` `dev/registry/pipeline/cli.py`
- `S02` `M` `dev/registry/pipeline/generated_export_inheritance.py`
- `S02` `M` `dev/registry/pipeline/generated_form_bridge.py`
- `S02` `M` `dev/registry/pipeline/historical_static_repair.py`
- `S02` `M` `dev/registry/pipeline/render_check.py`
- `S02` `M` `dev/release/alerting.py`
- `S02` `M` `dev/runtime_lifecycle/agent_live.py`
- `S02` `M` `dev/runtime_lifecycle/agent_startup_benchmark.py`
- `S02` `M` `dev/runtime_lifecycle/backend_probe.py`
- `S02` `M` `dev/runtime_lifecycle/caller_owned_root.py`
- `S02` `M` `dev/runtime_lifecycle/concurrent_sessions_probe.py`
- `S02` `M` `dev/runtime_lifecycle/frontend_startup_benchmark.py`
- `S02` `M` `dev/runtime_lifecycle/native_client_live.py`
- `S02` `M` `dev/runtime_lifecycle/reviewed_operation.py`
- `S02` `A` `dev/temporary_output.py`
- `S02` `M` `dev/test_runs/paths.py`
- `S02` `M` `dev/tests/test_development_temp_root.py`
- `S02` `M` `dev/tui/_artifacts.py`
- `S02` `M` `dev/tui/harness/sequences.py`
- `S02` `M` `native/desktop/frontend/scripts/modelo_fixtures.py`
- `S02` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S02` `verify:` `pytest dev/tests/test_development_temp_root.py dev/docs/tests/test_i18n.py dev/docs/tests/test_localized_surface_exclusions.py dev/locales/tests/test_signal.py` -> `pass`
- `S02` `verify:` `ruff check touched Python paths` -> `pass`
- `S02` `verify:` `ty check dev/temporary_output.py dev/_paths.py dev/docs/i18n.py dev/locales/signal_documentation_inventory.py` -> `pass`
- `S02` `verify:` `just report-code-health` -> `fail`
- `S01` `M` `dev/locales/signal_spelling_segments.py`
- `S01` `M` `dev/locales/signal_syntax.py`
- `S01` `M` `dev/locales/signal_tokens.py`
- `S01` `M` `dev/locales/signal_spelling_enrollment.py`
- `S01` `M` `dev/locales/tests/test_spelling_segments.py`
- `S01` `M` `dev/locales/tests/test_spelling_lexicon.py`
- `S01` `M` `dev/docs/casilla_page_rendering.py`
- `S01` `M` `dev/docs/tests/test_casilla_reference_presentation.py`
- `S01` `verify:` `pytest dev/docs/tests/test_casilla_reference_presentation.py dev/docs/tests/test_section_anchors.py dev/locales/tests/test_spelling_segments.py dev/locales/tests/test_spelling_lexicon.py` -> `pass`
- `S01` `verify:` `ruff check assigned locale and renderer paths` -> `pass`
- `S01` `verify:` `ruff format --check assigned locale and renderer paths` -> `pass`
- `S01` `verify:` `ty check assigned locale and renderer paths` -> `pass`
- `S01` `verify:` `just check-locales` -> `fail`
- `S04` `M` `dev/packaging/build_storage.py`
- `S04` `M` `dev/packaging/python_cohort.py`
- `S04` `M` `dev/packaging/release_cohort.py`
- `S04` `M` `dev/packaging/build_scratch_reclaim.py`
- `S04` `M` `dev/packaging/tests/test_build_storage.py`
- `S04` `M` `dev/packaging/tests/test_release_cohort.py`
- `S04` `M` `dev/packaging/tests/test_release_cohort_integration.py`
- `S04` `M` `dev/packaging/tests/test_build_scratch_reclaim.py`
- `S04` `M` `.vaultspec/skills/cadrumo-start/references/build-python-packaging-and-release.md`
- `S04` `verify:` `pytest dev/packaging/tests/test_build_storage.py dev/packaging/tests/test_release_cohort.py dev/packaging/tests/test_build_scratch_reclaim.py` -> `pass`
- `S04` `verify:` `pytest dev/packaging/tests/test_release_cohort_integration.py::test_real_clean_source_build_is_complete_and_reproducible` -> `pass`
- `S04` `verify:` `ruff check and format --check eight packaging paths` -> `pass`
- `S04` `verify:` `ty check eight packaging paths` -> `pass`
- `S04` `verify:` `just check-hooks` -> `pass`
- `S05` `M` `pyproject.toml`
- `S05` `M` `dev/test_runs/logging.py`
- `S05` `M` `dev/test_runs/tests/test_logging.py`
- `S05` `M` `.vaultspec/skills/cadrumo-start/references/build-python-packaging-and-release.md`
- `S05` `verify:` `uv run --no-sync pytest -q -n 0 -m integration dev/test_runs/tests/test_logging.py -k coverage` -> `pass`
- `S05` `verify:` `uv run --no-sync pytest -q -n 0 -m integration dev/test_runs/tests/test_logging.py -k 'not coverage'` -> `pass`
- `S05` `verify:` `uv run --no-sync pytest -q -n 0 dev/packaging/tests/test_preflight_recipe_selection.py::test_each_invocation_collects_a_non_empty_selection[campaign:preflight-tests]` -> `pass`
- `S05` `verify:` `uv run --no-sync ruff check dev/test_runs/logging.py dev/test_runs/tests/test_logging.py` -> `pass`
- `S05` `verify:` `uv run --no-sync ruff format --check dev/test_runs/logging.py dev/test_runs/tests/test_logging.py` -> `pass`
- `S05` `verify:` `uv run --no-sync ty check dev/test_runs/logging.py dev/test_runs/tests/test_logging.py` -> `pass`
- `S05` `verify:` `uv run --no-sync lint-imports --config .importlinter --no-cache` -> `pass`
- `S03` `A` `.vault/audit/2026-10-29-gate-findings-repair-audit.md`
- `S03` `M` `.vault/index/gate-findings-repair.index.md`
- `S03` `verify:` `just check-registry-gate` -> `pass`
- `S03` `verify:` `just check-bindings` -> `pass`
- `S03` `verify:` `just check-locales` -> `fail`
- `S03` `verify:` `just check-corpus-sidecars` -> `pass`
- `S03` `verify:` `just check-corpus-text` -> `pass`
- `S03` `verify:` `just check-security-full` -> `pass`
- `S03` `verify:` `just check-workflow-security` -> `pass`
- `S03` `verify:` `just check-hooks` -> `pass`
- `S03` `verify:` `just test-packaging-preflight` -> `fail`
- `S03` `verify:` `just test-coverage` -> `fail`
- `S03` `verify:` `just report-code-health` -> `pass`

## Notes

- `S02` 82 focused tests passed. Import scan kept all30 contracts, loaded5239 modules, zero hard findings; gate operational verdict unavailable because external governed source bytes changed. Final S03 rechecks.
- `S01` 88 owner tests plus numeric and real-dictionary controls passed; renderer B10. Canonical casilla generation passed58modelos/14154casillas. Final locale gate10109 affected cells, zero missing/tool/placeholder failures; remaining content and mixed-language inventory debt retained. External exact Google/Drive spellings excluded from authored repair.
- `S04` 100 focused tests and real two-build artifact reproducibility passed. Both independent medium cleanup findings resolved; false removal preserves exact path, primary failure, and SystemExit status with visible stderr. Native validator unchanged.
- `S05` 7 real coverage controls,16 logging controls and1 nested packaging case passed; threshold unchanged. Foreign commit c8c3e350b4 captured authored pyproject bootstrap while retiring llm extra; remaining foreign edits preserved. Secondary copied database78.8845 does not replace original recipe5.46/exit1. Independent review PASS.
- `S03` All11 exact commands completed;8 observed pass and3 nonzero outcomes retained. All8 packaging failures corrected with passing affected reruns;2 stale taxonomy failures fresh10pass. Coverage lifecycle fixed with7 realprobes,16 controls,1 nested collection; copies-only78.8845 remains secondary. Independent authored-repair reviewPASS. User explicitly accepted live-tree drift; residual locale debt and blocked scratch cleanup documented.
