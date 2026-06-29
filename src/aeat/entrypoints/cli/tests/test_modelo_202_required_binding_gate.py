"""CLI regression for Modelo 202 missing required-binding hard-stop."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ._profile_cli_support import create_quiet_profile
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_M202_INCN_BINDING = "modelo-202-2025-y-siguientes-incn-prior-12-months"
_M202_CUOTA_BASE_BINDING = "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
_M202_PRIOR_PAYMENTS_BINDING = "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores"
_MISSING_M202_BINDINGS = {
    _M202_INCN_BINDING,
    _M202_CUOTA_BASE_BINDING,
    _M202_PRIOR_PAYMENTS_BINDING,
}


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        try:
            yield
        finally:
            dispose_engine()


def _create_laura_taller_sol_profile() -> None:
    result = create_quiet_profile(
        "laura-taller-sol",
        "--entity-type",
        "legal_entity",
        "--legal-entity-form",
        "sl",
        "--tax-id",
        "B12345674",
        "--activity",
        "taller mecanico",
    )
    assert result.exit_code == 0, result.output


def test_laura_m202_not_ready_refuses_calculate_and_no_zero_artifact_is_reachable(tmp_path: Path) -> None:
    """Laura/Taller Sol cannot turn a not-ready M202 state into a zero draft/export/file."""
    _create_laura_taller_sol_profile()

    readiness = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "readiness",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
        ],
    )
    assert readiness.exit_code == 0, readiness.output
    readiness_payload = _payload(readiness.output)
    assert readiness_payload["ready"] is False
    assert readiness_payload["binding_ready"] is False
    assert {row["binding_id"] for row in readiness_payload["missing_bindings"]} == _MISSING_M202_BINDINGS

    created = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
        ],
    )
    assert created.exit_code == 0, created.output
    work_unit_id = _payload(created.output)["work_unit_id"]

    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
        ],
    )
    assert calculated.exit_code != 0, calculated.output
    error_payload = json.loads(calculated.output)
    error = error_payload["error"]
    assert error["code"] == "REFUSED_MODELO_REQUIRED_BINDINGS_MISSING"
    assert set(error["context"]["missing_bindings"]) == _MISSING_M202_BINDINGS
    assert "saved" not in calculated.output
    assert "Traceback" not in calculated.output

    status = invoke_cached_cli(["--format", "json", "app", "modelo", "work", "status", work_unit_id])
    assert status.exit_code == 0, status.output
    status_payload = _payload(status.output)
    assert status_payload["current_calculation_revision_id"] is None
    assert status_payload["filed_calculation_revision_id"] is None

    verify = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "verify",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
        ],
    )
    assert verify.exit_code != 0, verify.output
    assert "granted_verificado_completo" not in verify.output

    filed = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "file",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
        ],
    )
    assert filed.exit_code != 0, filed.output
    assert "presentado" not in filed.output

    export_path = tmp_path / "m202-laura-zero.txt"
    exported = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
            "--output",
            str(export_path),
        ],
    )
    assert exported.exit_code != 0, exported.output
    assert export_path.exists() is False
