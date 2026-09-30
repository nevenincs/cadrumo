"""Real CLI coverage for capital-goods register identity propagation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....tests.cli_envelope import unwrap_cli_result
from .._bienes_inversion_payloads import (
    BienesInversionDeclareResult,
    BienesInversionListResult,
    BienInversionDisposalPayload,
    BienInversionRecordPayload,
)
from ._runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_ACQUISITION_LEDGER_ID = "ledger-capital-good-1"
_PRORRATA_SECTOR_ID = "sector-services"

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Capital goods",
    "activities.description": "synthetic capital goods profile",
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
    result = invoke_cached_cli(
        ("--language", "en", "--format", "json", "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def test_bienes_inversion_declare_and_list_preserve_schema_two_identity_fields(tmp_path: Path) -> None:
    """Native worker preserves full records and refuses duplicate/incomplete writes."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-capital-goods", facts=_PROFILE_FACTS)
        command = (
            "app",
            "ledger",
            "bienes-inversion",
            "declare",
            "asset-machine",
            "--description",
            "Machine used by the services activity",
            "--acquisition-year",
            "2024",
            "--acquisition-ledger-id",
            _ACQUISITION_LEDGER_ID,
            "--cuota-soportada",
            "4200.00",
            "--prorrata-inicial",
            "80",
            "--kind",
            "mueble",
            "--sector",
            _PRORRATA_SECTOR_ID,
        )
        declared = _invoke(profile, *command, "--disposal-year", "2026", "--disposal-regime", "sujeta_no_exenta")
        assert declared.exit_code == 0, declared.output
        declared_payload = BienesInversionDeclareResult.model_validate(unwrap_cli_result(declared))
        expected = BienInversionRecordPayload(
            identifier="asset-machine",
            description="Machine used by the services activity",
            acquisition_year=2024,
            acquisition_ledger_id=_ACQUISITION_LEDGER_ID,
            prorrata_sector_id=_PRORRATA_SECTOR_ID,
            cuota_soportada="4200.00",
            prorrata_inicial_pct="80",
            kind="mueble",
            art108_elegible=True,
            disposal=BienInversionDisposalPayload(year=2026, regime="sujeta_no_exenta"),
            deduccion_efectuada="3360.00",
            schema_version="2",
        )
        assert declared_payload.record == expected
        assert declared_payload.count == 1

        duplicate = _invoke(profile, *command)
        incomplete = _invoke(profile, *command, "--disposal-year", "2026")
        for refused, reason in ((duplicate, "duplicate_identifier"), (incomplete, "disposal_incomplete")):
            assert refused.exit_code != 0, refused.output
            error = json.loads(refused.output)["error"]
            assert error["context"]["effect"] == "none"
            assert error["context"]["terminal_condition"] == "refused"
            assert error["context"]["refusal_code"] == "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION"
            assert error["context"]["reason"] == reason
            assert "4200.00" not in refused.output

        listed = _invoke(profile, "app", "ledger", "bienes-inversion", "list")
        assert listed.exit_code == 0, listed.output
        listed_payload = BienesInversionListResult.model_validate(unwrap_cli_result(listed))
        assert listed_payload.bucket_id == declared_payload.bucket_id
        assert listed_payload.count == 1
        assert listed_payload.rows == [expected]
