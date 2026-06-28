---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S65'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# add a production output-surface inventory gate for `_emit`, `_emit_envelope`, `typer.echo`, and direct writes

## Scope

- `src/aeat/entrypoints/cli/test_output_surface_inventory.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py`
- `src/aeat/application/wizard/_catalogue.py`
- `src/aeat/core/profile.py`
- `src/aeat/adapters/persistence/storage/sql/_orm.py`

## Description

- Add a production source inventory gate for direct CLI/diagnostic output calls.
- Route `ledger classify --reaffirm` output through `_emit_envelope` instead of direct `typer.echo`.
- Add a real CLI JSON regression for `ledger classify --reaffirm` so plain-text notices cannot precede JSON envelopes.
- Clean path-scoped `_ledger.py` lint issues encountered while touching the output path.
- Repair closeout defects surfaced by the focused privacy suite: wizard enrollment questions now persist to canonical `censo.*` keys, `SetupAnswers` accepts the postcode collected by the setup wizard, and secure-object lookup keys use hashed lookup storage instead of reversible encrypted natural keys.

## Outcome

S65 is implemented. The inventory gate now fails on unowned direct `typer.echo`, `print`, and stream-write output under the production CLI and diagnostics surfaces. The focused redaction contract suite passes after the adjacent wizard/profile/secure-object repairs.

## Notes

- `uv run pytest -q src/aeat/entrypoints/cli/test_output_surface_inventory.py src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py::test_classify_accepts_a_canonical_category_id src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py::test_classify_reaffirm_json_output_is_a_single_envelope` passed.
- `uv run ruff check src/aeat/entrypoints/cli/test_output_surface_inventory.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py` passed.
- `uv run ruff check src/aeat/core/profile.py src/aeat/application/wizard/_catalogue.py src/aeat/adapters/persistence/storage/sql/_orm.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_output_surface_inventory.py src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py` passed.
- `uv run pytest -q src/aeat/entrypoints/cli/test_output_surface_inventory.py src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py::test_classify_accepts_a_canonical_category_id src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py::test_classify_reaffirm_json_output_is_a_single_envelope src/aeat/application/wizard/test_setup_compiles.py src/aeat/application/wizard/test_setup_runtime.py::test_persist_answers_round_trip_via_project_answers src/aeat/application/wizard/test_widgets.py::test_postcode_preserves_leading_zero_string src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py` passed.
- `uv run pytest -q src/aeat/core/test_redaction.py src/aeat/core/test_logging.py src/aeat/core/test_output_rendering.py src/aeat/core/errors/test_envelope.py src/aeat/core/test_json_envelope_roundtrip.py src/aeat/core/observability/test_sink_redaction.py src/aeat/core/observability/test_store_redaction.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/entrypoints/cli/test_output_redaction_contract.py src/aeat/entrypoints/cli/test_json_schema_conformance.py src/aeat/entrypoints/cli/test_output_surface_inventory.py` passed.
