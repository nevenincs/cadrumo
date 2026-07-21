---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `CalcSheetsApplyResult`, `DriveConfig`, `PullResult`, `RowSetEdit`, `apply_export_plan`, `compute_from_pull`, `delete_session`, `load_client`, `load_drive_config`, `load_metadata`, `load_token`, `pull_operator_edits`, `resolve_active_profile`, `run_login_flow`, `save_client`, `save_drive_config`, `save_metadata`, `save_token` to `aeat.adapters.outbound.google.__all__` with eager re-exports so the 26 existing cross-package consumer site(s) can import from the facade

## Scope

- `src/aeat/adapters/outbound/google/__init__.py`

## Description

This record covers all three W01 facade-promotion Steps assigned to this dispatch: `W01.P03.S02` (`aeat.adapters.outbound.google`), `W01.P09.S09` (`aeat.adapters.outbound.aeat.sede`), and `W01.P07.S07` (`aeat.adapters.inbound.pdf`). None of the three owning packages had underscore-named promotion candidates, so every promotion was a straight eager re-export.

- Confirmed each symbol's defining private submodule via grep before editing.
- `aeat.adapters.outbound.google`: promoted `CalcSheetsApplyResult`, `apply_export_plan` (from `_calc_sheets_apply`), `RowSetEdit`, `PullResult`, `pull_operator_edits`, `compute_from_pull` (from `_calc_sheets_pull`), `DriveConfig` (from `_records`), `run_login_flow` (from `_oauth_flow`), `save_client`/`load_client`/`save_token`/`load_token`/`save_metadata`/`load_metadata`/`save_drive_config`/`load_drive_config`/`delete_session` (from `_session_store`), and `resolve_active_profile` (from `_active_profile`) into `aeat.adapters.outbound.google.__all__` with eager imports.
- `aeat.adapters.outbound.aeat.sede`: promoted `BrowserAdapterTypeError` (from `_errors`), `GroiSedeDriver` (from `_groi_check`), `NifIvaCheckSedeDriver` (from `_nif_iva_check`), and `filed_declaracion_observation_object_key`/`iva_compensation_wallet_observation_object_key` (from `_observation_store`) into `aeat.adapters.outbound.aeat.sede.__all__` with eager imports.
- `aeat.adapters.inbound.pdf`: promoted `TEXT_VALUE_GROUP` (already declared in `_label_regex.__all__` but not surfaced at package level), `extract_pages_text_concatenated`/`extract_pages_text_from_bytes`/`extract_pages_text_from_path`/`extract_pages_text_with_fast_path` (from `_pdfplumber`), and `sha256_file`/`source_pdf_reference_path` (from `_utils`) into `aeat.adapters.inbound.pdf.__all__` with eager imports.
- Verified no circular-import risk: none of the promoted submodules import the owning package's own `__init__`.
- Ran ruff check and ruff format --check on all three edited files (clean).
- Ran `python -c "import <pkg> as m; [getattr(m, n) for n in m.__all__]"` for each package to confirm every promoted symbol resolves (google 41 symbols, sede 55 symbols, pdf 13 symbols).
- Ran `uv run --no-sync pytest --collect-only -q src/aeat` (14593 collected, exit 0).
- Committed each package's facade separately via explicit pathspec.

## Outcome

All three facades now export their cross-package-consumed symbols directly. No consumer-site rewrites were performed (Wave W02 scope). Commits: `a5571b9a8` (`aeat.adapters.outbound.google`), `9d6af8015` (`aeat.adapters.outbound.aeat.sede`), `dedd12eb8` (`aeat.adapters.inbound.pdf`).

## Notes

No underscore-named promotion candidates existed for these three owning packages (unlike several sibling W01 phases), so no per-symbol disposition judgment was required. An unrelated, pre-existing uncommitted change to `src/aeat/adapters/outbound/google/tests/test_package_module_allowlist.py` (a peer's allowlist entry for `_calc_sheets_support.py`) was observed in the google package directory during the WIP check; it was left untouched as out-of-scope peer work.
