"""Modelo 100 readiness must expose actionable missing calculation bindings."""

from __future__ import annotations

import json

import pytest

from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MODELO = "100"
_YEAR = "2025"
_PERIOD = "0A"
_REVISION = "2025"


def _create_natural_person_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Readiness",
            "activities.description": "design",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "directa_normal",
        },
    )


def test_modelo_100_readiness_filters_ledger_bindings_after_clean_preflight() -> None:
    """Profile-ready M100 still blocks only on unresolved non-ledger bindings.

    ``bindings list --missing`` remains the raw binding-discovery surface. The
    readiness report is the operator gate: ledger-sourced bindings become
    available once the real ledger preflight passes, while manual, relation, and
    previous-filing inputs remain actionable blockers.
    """

    _create_natural_person_profile()

    readiness = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "readiness",
            "--modelo", _MODELO,
            "--revision-id", _REVISION,
            "--year", _YEAR,
            "--period", _PERIOD,
        ],
    )  # fmt: skip
    assert readiness.exit_code == 0, readiness.output
    readiness_payload = _payload(readiness.output)

    missing = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "bindings", "list",
            "--modelo", _MODELO,
            "--year", _YEAR,
            "--period", _PERIOD,
            "--missing",
        ],
    )  # fmt: skip
    assert missing.exit_code == 0, missing.output
    bindings_payload = _payload(missing.output)

    readiness_missing = {row["binding_id"]: row for row in readiness_payload["missing_bindings"]}
    bindings_missing_by_id = {row["binding_id"]: row for row in bindings_payload["bindings"]}
    bindings_missing_ids = set(bindings_missing_by_id)

    assert readiness_payload["profile_ready"] is True
    assert readiness_payload["ledger_ready"] is True
    assert readiness_payload["ready"] is False
    assert readiness_payload["binding_ready"] is False
    envelope = json.loads(readiness.output)
    notices_by_code = {notice["code"]: notice for notice in envelope["notices"]}
    ledger_notice = notices_by_code["modelo.readiness.ledger_preflight_scope"]
    assert ledger_notice["context"]["missing_bindings"] == str(len(readiness_missing))
    assert "modelo.readiness.export_unsupported" not in notices_by_code
    assert readiness_missing.keys() <= bindings_missing_ids
    preflight_resolved_ids = bindings_missing_ids - set(readiness_missing)
    assert preflight_resolved_ids
    preflight_resolved_sources = {bindings_missing_by_id[binding_id]["source"] for binding_id in preflight_resolved_ids}
    assert {
        "ledger_renta_gastos_estimacion_directa_aggregation",
        "ledger_renta_income_aggregation",
    } <= preflight_resolved_sources
    assert all(source.startswith("ledger_") for source in preflight_resolved_sources)
    assert {
        "manual_input",
        "relation_prefill",
        "previous_filing",
    } <= {row["source"] for row in readiness_missing.values()}
    assert all(not row["source"].startswith("ledger_") for row in readiness_missing.values())

    text_readiness = invoke_cached_cli(
        [
            "app",
            "modelo",
            "readiness",
            "--modelo",
            _MODELO,
            "--revision-id",
            _REVISION,
            "--year",
            _YEAR,
            "--period",
            _PERIOD,
        ],
    )
    assert text_readiness.exit_code == 0, text_readiness.output
    assert "ready\tFalse" in text_readiness.output
    assert "source_binding_ready\tFalse" in text_readiness.output
    assert "ledger_ready_scope\ttransaction_preflight_only" in text_readiness.output
    assert "export_ready\tTrue" in text_readiness.output
    assert "export_refusal\t\n" in text_readiness.output
    assert "finish_line\texport verified-complete revision via 'aeat app modelo export'" in text_readiness.output
    assert "readiness_note\tledger_ready only means" in text_readiness.output
    assert (
        "missing_bindings_command\taeat app modelo bindings list --modelo 100 --year 2025 --period 0A --missing"
    ) in text_readiness.output
