"""A verification that stopped before locking its revision is reported as unsettled, not as a denial.

Verification saves its report before it marks the revision verified. A run that
stops between the two leaves the operator's own draft beside a granting report.
That outcome is not known to have completed, so commands that need a settled
revision say so with a registered error every frontend receives from the same
registered read, and ``work verify`` remains the way to settle it. A revision
outside the operator's reach is still refused without saying whether it exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_cli_backend as _isolated_cli_backend
from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ....tests.cli_envelope import require_error_document
from ._modelo_review_package_support import seed_exportable_modelo_revision
from .modelo_profile_seed import ProfileSeeder, invoke_seeded_profile_cli, seed_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["_isolated_cli_backend", "seed_profile"]

_INPUTS = {validated_casilla_id("03"): "180.25", validated_casilla_id("06"): "12.10"}
_INCOMPLETE = "ERROR_MODELO_VERIFICATION_OUTCOME_INCOMPLETE"


@pytest.fixture(autouse=True)
def _operator(seed_profile: ProfileSeeder) -> None:
    seed_profile(label="interrupted verifier", facts={"withholding.colegio_concertado": "false"})


def _interrupted_verification(operation: PinnedAuthorityOperation) -> tuple[str, str]:
    """Leave the persisted state of a verification stopped after its report and before its lock."""
    work_unit_id, calculation_revision_id = seed_exportable_modelo_revision(
        input_values_by_casilla_id=_INPUTS, operation=operation
    )
    revisions = CalculationRevisionCatalogueRepository()
    catalogue = revisions.load()
    verified = catalogue.get(calculation_revision_id)
    assert verified is not None
    draft = CalculationRevision.model_validate(
        verified.model_dump(mode="python")
        | {"state": CalculationRevisionState.BORRADOR, "verified_at": None, "verified_by": None}
    )
    revisions.save(upsert_calculation_revision(catalogue, draft))
    reports = VerificationReportCatalogueRepository().load().for_calculation_revision(calculation_revision_id)
    assert [report.granted_verificado_completo for report in reports] == [True]
    return work_unit_id, calculation_revision_id


def _error(args: list[str]) -> dict[str, Any]:
    result = invoke_seeded_profile_cli(["--format", "json", *args])
    assert result.exit_code != 0, result.output
    error = require_error_document(result.output)["error"]
    assert isinstance(error, dict)
    return error


def test_commands_needing_a_settled_revision_report_the_unfinished_verification(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    _work_unit_id, calculation_revision_id = _interrupted_verification(operation)
    out = tmp_path / "modelo-111.txt"

    for args in (
        ["app", "modelo", "export", "--revision", calculation_revision_id, "--output", str(out)],
        ["app", "modelo", "work", "file", calculation_revision_id],
    ):
        error = _error(args)
        assert error["code"] == _INCOMPLETE, (args, error)
        assert error["code"] != "REFUSED_PROFILE_ACCESS"
    assert not out.exists()


def test_verify_is_admitted_to_run_again_on_an_unfinished_verification(*, operation: PinnedAuthorityOperation) -> None:
    """Selection hands the draft to verification instead of refusing the one command that settles it."""
    _work_unit_id, calculation_revision_id = _interrupted_verification(operation)

    verified = invoke_seeded_profile_cli(
        ["--format", "json", "app", "modelo", "work", "verify", calculation_revision_id]
    )

    document = json.loads(verified.output)
    error = document.get("error")
    if error is None:
        assert document["result"]["calculation_revision_id"] == calculation_revision_id
        return
    # This planted revision carries no calculation provenance, so the verifier
    # itself may stop it; what matters is that the verifier ran.
    assert error["code"] not in {_INCOMPLETE, "REFUSED_PROFILE_ACCESS", "REFUSED_RUNTIME_FRONTEND"}, error
    assert error["context"]["terminal_condition"] in {"failed", "refused"}, error
    assert error["context"]["operation_id"], error


def test_an_unknown_revision_is_still_refused_without_naming_its_state() -> None:
    error = _error(["app", "modelo", "work", "file", "f" * 64])
    assert error["code"] != _INCOMPLETE
