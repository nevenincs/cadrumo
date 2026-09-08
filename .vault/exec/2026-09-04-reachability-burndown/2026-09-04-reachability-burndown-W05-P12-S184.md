---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:97365a86f13c2e6a8ab5dad0953d407328239c428f530ca159eb9588b8d28d55'
step_id: 'S184'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the raw capture_declaration implementation and the one-call capture_filed_declaration_observation wrapper after amending the identity decision to make DeclaracionesRegisterSession.capture_observation the sole declarations-register capture owner; move the early empty-identity refusal onto that live method, migrate tests to normalized artefact capture, and preserve exact-row, cotejo, CSV, PDF-response, and walker SedeCapture guarantees.

## Scope

- `declarations-register capture facades`
- `session owner`
- `live and PDF-contract tests`
- `justificante identity ADR/reference and live reachability measurement`

## Changes

- `M` `.vault/adr/2026-08-07-justificante-identity-matching-adr.md`
- `M` `.vault/reference/2026-08-07-justificante-identity-matching-reference.md`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations_capture.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/_declarations_support.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_live.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part3.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_pdf_response_contract.py`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/outbound/aeat/sede/tests/test_pdf_response_contract.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part3.py::test_register_capture_empty_nif_carries_translated_message` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail`

- `M` `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/application_links/*filed-declarations-observation*.toml`
- `A` `dev/quality/application_link_consumers.py`
- `A` `dev/quality/tests/test_application_link_consumers.py`
- `M` `dev/quality/suite.py`
- `M` `justfile`
- `verify:` `uv run --no-sync pytest -q -n0 -m unit dev/quality/tests/test_application_link_consumers.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.application_link_consumers` -> `pass`
- `verify:` independent S184 re-review -> `pass`

## Notes

The exact detector reports 348 unused symbols and 18 orphaned tests in the live shared tree while no longer reporting either retired declaration-capture symbol. The broader submitted-file tests remain red in concurrent registry/export-layout work, and the exact-row browser test cannot execute because the configured Playwright Chromium binary is absent.
