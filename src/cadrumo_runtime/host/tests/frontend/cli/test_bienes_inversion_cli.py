"""Real CLI coverage for capital-goods register identity propagation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.entrypoints.cli.bienes_inversion_results import (
    BienesInversionDeclareResult,
    BienesInversionListResult,
    BienInversionDisposalPayload,
    BienInversionRecordPayload,
)
from cadrumo.tests.cli_envelope import unwrap_cli_result

from ...native_commands.runtime_profile_cli_fixture import native_cli_profile_scope
from ...native_profile_facts import native_general_iva_facts
from .profile_cli_support import invoke_native_profile

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_ACQUISITION_LEDGER_ID = "ledger-capital-good-1"
_PRORRATA_SECTOR_ID = "sector-services"
_ACQUISITION_YEAR = filing_year_envelope().floor
_DISPOSAL_YEAR = filing_year_envelope().horizon

_PROFILE_FACTS = native_general_iva_facts()


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
            str(_ACQUISITION_YEAR),
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
        declared = invoke_native_profile(
            profile, *command, "--disposal-year", str(_DISPOSAL_YEAR), "--disposal-regime", "sujeta_no_exenta"
        )
        assert declared.exit_code == 0, declared.output
        declared_payload = BienesInversionDeclareResult.model_validate(unwrap_cli_result(declared))
        expected = BienInversionRecordPayload(
            identifier="asset-machine",
            description="Machine used by the services activity",
            acquisition_year=_ACQUISITION_YEAR,
            acquisition_ledger_id=_ACQUISITION_LEDGER_ID,
            prorrata_sector_id=_PRORRATA_SECTOR_ID,
            cuota_soportada="4200.00",
            prorrata_inicial_pct="80",
            kind="mueble",
            art108_elegible=True,
            disposal=BienInversionDisposalPayload(year=_DISPOSAL_YEAR, regime="sujeta_no_exenta"),
            deduccion_efectuada="3360.00",
            schema_version="2",
        )
        assert declared_payload.record == expected
        assert declared_payload.count == 1

        duplicate = invoke_native_profile(profile, *command)
        incomplete = invoke_native_profile(profile, *command, "--disposal-year", str(_DISPOSAL_YEAR))
        for refused, reason in ((duplicate, "duplicate_identifier"), (incomplete, "disposal_incomplete")):
            assert refused.exit_code != 0, refused.output
            error = json.loads(refused.output)["error"]
            assert error["context"]["effect"] == "none"
            assert error["context"]["terminal_condition"] == "refused"
            assert error["context"]["refusal_code"] == "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION"
            assert error["context"]["reason"] == reason
            assert "4200.00" not in refused.output

        listed = invoke_native_profile(profile, "app", "ledger", "bienes-inversion", "list")
        assert listed.exit_code == 0, listed.output
        listed_payload = BienesInversionListResult.model_validate(unwrap_cli_result(listed))
        assert listed_payload.bucket_id == declared_payload.bucket_id
        assert listed_payload.count == 1
        assert listed_payload.rows == [expected]
