---
tags:
  - '#audit'
  - '#live-filed-history-calendar-modelo'
date: '2026-06-12'
modified: '2026-06-12'
related: []
---

# `live-filed-history-calendar-modelo` Code Review

## LIVE-FILED-HISTORY-001 | HIGH | IVA evidence CLI passes raw target period string to typed service

`src/aeat/entrypoints/cli/_app_live.py` line 585 forwards `target_period` directly from the Typer string option into `capture_iva_remote_state`, whose contract expects `core.Period` and immediately dereferences `target_period.filing_year`. A valid command such as `app live iva-wallet pull-evidence --target-year 2026 --target-period 2T` can therefore fail as an internal attribute error instead of validating the operator period input. Recommended fix: parse with `_required_live_period_option(target_period, year=target_year)` before calling the application service, and add a CLI regression that exercises the command path or a focused callback-level assertion.

## LIVE-FILED-HISTORY-002 | MEDIUM | Filed-history evidence stamping overwrites existing official filing evidence

`src/aeat/application/live/_filed_observation_persistence.py` lines 189-206 only treats an existing stamp as idempotent when it is `AEAT_LIVE_CAPTURE` with the same CSV. If the current `ModeloRecord` already carries another official `ExternalEvidenceKind`, such as `AEAT_JUSTIFICANTE_PDF`, the filed-history pull replaces that evidence with `AEAT_LIVE_CAPTURE` and emits a new `MODELO_LIVE_EVIDENCE_STAMPED` event. The cross-period evidence gate treats justificante PDF and live capture as peer justificante-verified official evidence, so silently rewriting the existing stamp loses provenance and makes re-enrollment non-idempotent across equivalent evidence channels. Recommended fix: if `current.aeat_accepted` and `current.external_evidence` is already present, no-op when it references the same CSV under any official justificante-verified kind, and refuse or report a conflict when the existing reference differs; cover both cases with real repository tests.

## LIVE-FILED-HISTORY-003 | INFO | Remediation review found no remaining blockers

Remediation review confirmed both prior findings are fixed:

- `iva-wallet pull-evidence` resolves `--target-period` through `_required_live_period_option(..., year=target_year)` before invoking `capture_iva_remote_state`, preserving the backend `core.Period` contract.
- Filed-history justificante enrollment preserves same-CSV accepted official evidence, reports different-CSV accepted official evidence as a conflict, and does not overwrite or emit a new stamp event for either no-write branch.

Focused verification after remediation:

- `uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py -m "integration or not integration" -q` passed with 20 tests.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py -k "filed or pull_evidence_resolves_target_period" -m "integration or not integration" -q` passed with 12 selected tests.
- `uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 128 tests.
- `uv run pytest src/aeat/entrypoints/cli/tests -k "schema or payload" -m "integration or not integration" -q` passed with 274 selected tests.
- `uv run ruff check` passed over the touched live, CLI, payload, and regression-test files.
