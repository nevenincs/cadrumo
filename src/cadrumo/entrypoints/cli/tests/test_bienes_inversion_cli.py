"""Real CLI coverage for capital-goods register identity propagation."""

from __future__ import annotations

import json

import pytest

from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_envelope import unwrap_cli_result
from ....tests.cli_runner import invoke_cached_cli
from .._bienes_inversion_payloads import (
    BienesInversionDeclareResult,
    BienesInversionListResult,
    BienInversionRecordPayload,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "00000000-0000-4000-8000-000000000000"
_ACQUISITION_LEDGER_ID = "ledger-capital-good-1"
_PRORRATA_SECTOR_ID = "sector-services"

_isolated_backend = active_profile_isolated_backend_fixture(bucket_id=_PROFILE_ID)


def test_bienes_inversion_declare_and_list_preserve_schema_two_identity_fields() -> None:
    """Declare/list persist the explicit acquisition ledger and prorrata sector IDs."""
    declared = invoke_cached_cli(
        [
            "--format",
            "json",
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
        ],
    )
    assert declared.exit_code == 0, declared.output
    assert json.loads(declared.output)["status"] == "success"
    declared_payload = BienesInversionDeclareResult.model_validate(unwrap_cli_result(declared))
    assert declared_payload.record.acquisition_ledger_id == _ACQUISITION_LEDGER_ID
    assert declared_payload.record.prorrata_sector_id == _PRORRATA_SECTOR_ID

    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "bienes-inversion", "list"])
    assert listed.exit_code == 0, listed.output
    listed_payload = BienesInversionListResult.model_validate(unwrap_cli_result(listed))
    assert listed_payload.count == 1
    persisted = listed_payload.rows[0]
    assert persisted.identifier == "asset-machine"
    assert persisted.acquisition_ledger_id == _ACQUISITION_LEDGER_ID
    assert persisted.prorrata_sector_id == _PRORRATA_SECTOR_ID

    round_tripped = BienInversionRecordPayload.model_validate_json(persisted.model_dump_json())
    assert round_tripped == persisted
