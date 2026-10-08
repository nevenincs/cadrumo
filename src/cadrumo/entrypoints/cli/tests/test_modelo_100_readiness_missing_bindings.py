"""Modelo 100 readiness must expose actionable missing calculation bindings."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_MODELO = "100"
_YEAR = "2025"
_PERIOD = "0A"
_REVISION = "2025"


def test_modelo_100_readiness_filters_ledger_bindings_after_clean_preflight(tmp_path: Path) -> None:
    """Profile-ready M100 still blocks only on unresolved non-ledger bindings.

    ``bindings list --missing`` remains the raw binding-discovery surface. The
    readiness report is the operator gate: ledger-sourced bindings become
    available once the real ledger preflight passes, while manual, relation, and
    previous-filing inputs remain actionable blockers.
    """

    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label="native-m100-readiness",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.tax_id": "12345678Z",
                "identity.name": "Operator",
                "identity.surnames": "Readiness",
                "activities.description": "design",
                "censo.activity_start_date": "2024-01-01",
                "contact.postcode": "28013",
                "tax_residence.jurisdiction_scope": "common_regime",
                "tax_residence.ccaa": "madrid",
                "taxpayer_type.irpf_income_categories": "actividad_economica",
                "irpf.estimation_regime": "directa_normal",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        assert profile.label is not None

        def invoke(args: list[str]) -> Result:
            assert profile.label is not None
            close_active_bucket_session()
            return invoke_cached_cli(
                ("--profile", profile.label, "--profile-secrets-stdin", *args),
                input=json.dumps({"profile_passphrase": profile.passphrase}),
            )

        readiness = invoke(
        [
            "--format", "json",
            "app", "modelo", "readiness",
            "--modelo", _MODELO,
            "--revision-id", _REVISION,
            "--year", _YEAR,
            "--period", _PERIOD,
        ],
    )  # fmt: skip
        assert readiness.exit_code == 2, readiness.output
        readiness_payload = _payload(readiness.output)

        missing = invoke(
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
        text_readiness = invoke(
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
            ]
        )

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

    assert text_readiness.exit_code == 2, text_readiness.output
    assert "ready\tFalse" in text_readiness.output
    assert "source_binding_ready\tFalse" in text_readiness.output
    assert "ledger_ready_scope\ttransaction_preflight_only" in text_readiness.output
    assert "export_ready\tTrue" in text_readiness.output
    assert "export_refusal\t\n" in text_readiness.output
    assert "readiness_note\tYour records passed this period's checks" in text_readiness.output
    assert "missing_bindings_command" not in text_readiness.output
    assert "finish_line" not in text_readiness.output
    assert all("operator_action" not in row for row in readiness_missing.values())
