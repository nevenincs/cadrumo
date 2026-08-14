"""Real CLI coverage for capital-goods register identity propagation."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.workflow import workflow_state_repository
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .._bienes_inversion_payloads import (
    BienesInversionDeclareResult,
    BienesInversionListResult,
    BienInversionRecordPayload,
)
from .envelope_helpers import unwrap_cli_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "00000000-0000-4000-8000-000000000000"
_ACQUISITION_LEDGER_ID = "ledger-capital-good-1"
_PRORRATA_SECTOR_ID = "sector-services"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(_PROFILE_ID),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID),
        )
        yield


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
