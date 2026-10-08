"""Native profile-worker journey for registered Modelo 036 commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....core.config import override_settings
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Modelo 036",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            (
                "--language",
                "en",
                "--format",
                "json",
                "--profile",
                profile.label,
                "--profile-secrets-stdin",
                *command,
            ),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result


def test_native_m036_five_commands_round_trip_real_worker_records(tmp_path: Path) -> None:
    """All five public commands use the installed worker and retain canonical fields."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-m036-operation", facts=_PROFILE_FACTS)

        alta = _invoke(
            profile,
            "app",
            "modelo",
            "m036",
            "alta",
            "--declared-on",
            "2025-01-01",
            "--sede-justificante",
            "receipt-alta",
            "--note",
            "Alta note",
        )
        assert alta.exit_code == 0, alta.output
        alta_result = unwrap_cli_result(alta)
        assert alta_result["event_kind"] == "alta"
        assert alta_result["declared_on"] == "2025-01-01"
        assert alta_result["sede_justificante"] == "receipt-alta"
        assert alta_result["note"] is None
        alta_id = alta_result["declaration_id"]
        assert isinstance(alta_id, str) and len(alta_id) == 64

        modificacion = _invoke(
            profile,
            "app",
            "modelo",
            "m036",
            "modificacion",
            "--declared-on",
            "2025-03-01",
            "--sede-justificante",
            "receipt-modificacion",
            "--note",
            "Modification note",
        )
        assert modificacion.exit_code == 0, modificacion.output
        modificacion_result = unwrap_cli_result(modificacion)
        assert modificacion_result["event_kind"] == "modificacion"
        assert modificacion_result["note"] is None

        baja = _invoke(
            profile,
            "app",
            "modelo",
            "m036",
            "baja",
            "--declared-on",
            "2026-01-01",
            "--sede-justificante",
            "receipt-baja",
            "--note",
            "Baja note",
        )
        assert baja.exit_code == 0, baja.output
        baja_result = unwrap_cli_result(baja)
        assert baja_result["event_kind"] == "baja"
        assert baja_result["note"] is None

        listed = _invoke(profile, "app", "modelo", "m036", "list")
        assert listed.exit_code == 0, listed.output
        list_result = unwrap_cli_result(listed)
        assert list_result["declaration_count"] == 3
        rows = list_result["declarations"]
        recorded = {
            "alta": (alta_result, "Alta note"),
            "modificacion": (modificacion_result, "Modification note"),
            "baja": (baja_result, "Baja note"),
        }
        assert [row["declaration_id"] for row in rows] == sorted(
            entry[0]["declaration_id"] for entry in recorded.values()
        )
        for row in rows:
            record, note = recorded[row["event_kind"]]
            assert row["declaration_id"] == record["declaration_id"]
            assert row["bucket_id"] == record["bucket_id"]
            assert row["profile_id"] == record["profile_id"]
            assert row["declared_on"] == record["declared_on"]
            assert row["recorded_at"] == record["recorded_at"]
            assert row["sede_justificante"] == record["sede_justificante"]
            assert row["note"] == note

        viewed = _invoke(profile, "app", "modelo", "m036", "view", alta_id)
        assert viewed.exit_code == 0, viewed.output
        view_result = unwrap_cli_result(viewed)
        assert view_result["declaration_id"] == alta_id
        assert view_result["event_kind"] == "alta"
        alta_row = next(row for row in rows if row["declaration_id"] == alta_id)
        assert view_result["bucket_id"] == alta_row["bucket_id"]
        assert view_result["profile_id"] == alta_row["profile_id"]
        assert view_result["declared_on"] == alta_row["declared_on"]
        assert view_result["recorded_at"] == alta_row["recorded_at"]
        assert view_result["sede_justificante"] == alta_row["sede_justificante"]
        assert view_result["note"] == "Alta note"

        missing = _invoke(profile, "app", "modelo", "m036", "view", "0" * 64)
        assert missing.exit_code != 0, missing.output
        error = require_error_document(missing.output)["error"]
        context = error["context"]
        assert error["category"] == "REFUSED"
        assert context["reason"] == "REFUSED_M036_DECLARATION_NOT_FOUND"
        assert context["refusal_code"] == "REFUSED_M036_DECLARATION_NOT_FOUND"
        assert context["terminal_condition"] == "refused"
        assert context["effect"] == "none"
        assert context["operation_id"]
        assert context["value"] == "0" * 64
