---
tags:
  - '#exec'
  - '#export-parity'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:944d3343c446cd22ca73633f3226a8592f0bd46d1f159de1b19059fd0fb91630'
related:
  - "[[2026-09-26-export-parity-plan]]"
---

# `export-parity` ledger

## Changes

- `S01` `M` `src/cadrumo/domain/filing/software_identity.py`
- `S01` `M` `src/cadrumo/application/modelo/export.py`
- `S01` `M` `src/cadrumo/application/modelo/export_ports.py`
- `S01` `M` `src/cadrumo/application/modelo/quickfile.py`
- `S01` `M` `src/cadrumo/entrypoints/adapter_composition.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/_modelo_export_cli.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `S01` `M` `src/cadrumo/domain/modelos/errors.py`
- `S01` `M` `src/cadrumo/core/errors/registry/_domain_part3.py`
- `S01` `M` `dev/acceptance/iva/cli_journey.py`
- `S01` `M` `dev/acceptance/iva/installed_m303_evidence_journey.py`
- `S01` `M` `docs/_sequences`
- `S01` `A` `.vault/adr/2026-09-26-export-parity-adr.md`
- `S01` `verify:` `pytest export verb, M303 surface parity, output paths, e2e ledger, TUI modal and evidence screen, filing and domain suites` -> `pass`
- `S01` `verify:` `just check-types` -> `pass`
- `S01` `verify:` `docs sequences refreshed by generator; check divergences resolved` -> `pass`
- `S01` `verify:` `installed-CLI M303 2025 lane export parsed back to oracle` -> `pass`
- `S01` `by:` `orchestrator`
- `S02` `M` `src/cadrumo/domain/calculations/registry/export_parse.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/fixed_width_codec.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/schema_exports.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/tests/test_fixed_width_codec.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/tests/test_filing_envelope_declaration.py`
- `S02` `M` `src/cadrumo/application/filing/tests/test_modelo_303_exonerado_390_refusal.py`
- `S02` `verify:` `pytest registry, filing, modelo, adapter suites: 5220 passed, 57 environmental browser-launch failures unchanged` -> `pass`
- `S02` `verify:` `real M303 2025 file parses to iva.resultado 10.50; M390 2025 parses 360 casillas` -> `pass`
- `S02` `by:` `orchestrator`
- `S07` `M` `src/cadrumo/core/atomic_write.py`
- `S07` `M` `src/cadrumo/core/tests/test_atomic_write.py`
- `S07` `M` `src/cadrumo/application/modelo/export.py`
- `S07` `M` `src/cadrumo/application/modelo/operator_inputs.py`
- `S07` `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_calculations_command_specs.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/_modelo_export_cli.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_nonwork_command_specs.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/modelo/lifecycle.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/modelo/view/overview.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_overview.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_export_output_paths.py`
- `S07` `M` `src/cadrumo/locales/en/cli.yml`
- `S07` `M` `src/cadrumo/locales/es/cli.yml`
- `S07` `M` `src/cadrumo/locales/ca/cli.yml`
- `S07` `M` `src/cadrumo/locales/hu/cli.yml`
- `S07` `M` `src/cadrumo/locales/en/common.yml`
- `S07` `M` `src/cadrumo/locales/es/common.yml`
- `S07` `M` `src/cadrumo/locales/ca/common.yml`
- `S07` `M` `src/cadrumo/locales/hu/common.yml`
- `S07` `verify:` `pytest entrypoints/tui/modelo + export verb + surface parity + output paths + application/modelo + atomic_write (1332)` -> `pass`
- `S07` `verify:` `just check-types` -> `pass`
- `S07` `verify:` `python -m dev.docs.sequences check` -> `pass`
- `S07` `verify:` `python -m dev.locales status --check (baseline-identical 5 unassigned findings)` -> `pass`
- `S08` `A` `src/cadrumo/application/modelo/export_sink.py`
- `S08` `M` `src/cadrumo/application/modelo/export.py`
- `S08` `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `S08` `M` `src/cadrumo/entrypoints/cli/_modelo_export_cli.py`
- `S08` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_export_output_paths.py`
- `S08` `A` `src/cadrumo/adapters/outbound/workbook/__init__.py`
- `S08` `A` `src/cadrumo/adapters/outbound/workbook/calc_sheets_xlsx.py`
- `S08` `A` `src/cadrumo/adapters/outbound/workbook/tests/__init__.py`
- `S08` `A` `src/cadrumo/adapters/outbound/workbook/tests/test_calc_sheets_xlsx.py`
- `S08` `A` `src/cadrumo/adapters/outbound/workbook/tests/test_calc_sheets_workbook_export.py`
- `S08` `M` `src/cadrumo/adapters/outbound/google/_calc_sheets_apply_formatting.py`
- `S08` `M` `src/cadrumo/adapters/outbound/google/_calc_sheets_apply_values.py`
- `S08` `M` `src/cadrumo/adapters/outbound/google/calc_sheets_apply.py`
- `S08` `A` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_transport_parity.py`
- `S08` `M` `src/cadrumo/application/storage/calc_sheets/__init__.py`
- `S08` `M` `src/cadrumo/application/storage/calc_sheets/export_tables.py`
- `S08` `M` `src/cadrumo/application/storage/calc_sheets/records.py`
- `S08` `A` `src/cadrumo/application/storage/calc_sheets/workbook_cells.py`
- `S08` `A` `src/cadrumo/application/storage/calc_sheets/workbook_export.py`
- `S08` `A` `src/cadrumo/application/storage/calc_sheets/tests/test_workbook_export.py`
- `S08` `M` `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_command_specs.py`
- `S08` `M` `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_payloads.py`
- `S08` `M` `src/cadrumo/entrypoints/cli/modelo_spreadsheet_cli.py`
- `S08` `A` `src/cadrumo/entrypoints/cli/tests/test_modelo_spreadsheet_export.py`
- `S08` `M` `src/cadrumo/locales/en/cli.yml`
- `S08` `M` `src/cadrumo/locales/es/cli.yml`
- `S08` `M` `src/cadrumo/locales/ca/cli.yml`
- `S08` `M` `src/cadrumo/locales/hu/cli.yml`
- `S08` `M` `dev/quality/metadata/import_load_targets.json`
- `S08` `verify:` `pytest (unit or integration) export surfaces + TUI modelo + application/modelo + atomic_write (1637 pass; 1 pre-existing TUI timing failure reproduced on ef8ad07c)` -> `pass`
- `S08` `verify:` `pytest (unit or integration) CLI contract/schema/help suites + new spreadsheet export tests (656)` -> `pass`
- `S08` `verify:` `pytest adapters/outbound/workbook + google + calc_sheets (411)` -> `pass`
- `S08` `verify:` `ty check on changed modules` -> `pass`
- `S08` `verify:` `just check-symbol-usage / check-export-consumption / check-module-reachability back to baseline counts` -> `pass`
- `S08` `verify:` `python -m dev.locales status --check baseline-identical` -> `pass`
- `S08` `verify:` `live: aeat app modelo spreadsheet export 303 2025 1T, refusal on existing file, --replace` -> `pass`

## Notes

- `S07` No-overwrite half of S07 landed in 6869e1a2; the typed export artefact contract half remains open, so S07 stays unchecked.
- `S07` Full entrypoint suite: 39 failures outside export, all environmental (no PowerShell, no Chrome channel, no local LLM) or load-dependent and passing in isolation.
- `S08` Committed in 1af2b083. just check-types crashed (ty produced no report under host load), not a type finding; ty run directly on the changed modules is clean.
- `S08` S07 verification in 6869e1a2 ran only the default unit lane; the integration tests of the same files were re-run here and pass.
- `S08` TUI offline-workbook export is not yet wired (tracked for S10); S07's typed sink landed here, so S07 closes with it.
