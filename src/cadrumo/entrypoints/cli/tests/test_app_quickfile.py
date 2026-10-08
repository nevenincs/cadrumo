"""Pure Quickfile CLI payload and notice-contract tests.

The exact-profile worker journey has a separate native acceptance node. This
module keeps the portable public-output contracts independent of profile custody.
"""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.tests.secure_sql import isolated_cli_backend as _isolated_cli_backend
from ....application.modelo.quickfile import QuickfileStage, QuickfileStageStatus
from ....application.modelo.quickfile_operation_contracts import (
    QuickfileReadinessSummary,
    QuickfileStageError,
    QuickfileStageSnapshot,
)
from ....application.modelo.quickfile_operation_projections import QuickfileProjection
from ....application.operations.public_period import PublicPeriod
from ....core.errors.error_codes import get_registered_error_code_by_code
from ....core.json_contract import Notice, NoticeSeverity
from ....core.operations import OperationEffect
from ....core.period import Period
from .._app_quickfile import _stage_notice
from .._app_quickfile_payloads import (
    QuickfileReadinessSummaryPayload,
    QuickfileResultPayload,
    QuickfileStageOutcomePayload,
)

__all__ = ["_isolated_cli_backend"]
pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _stopped_projection() -> QuickfileProjection:
    """Build a complete safe refusal projection with all five ordered stages."""
    error = get_registered_error_code_by_code("REFUSED_MODELO_PROFILE_READINESS")
    return QuickfileProjection(
        profile_id=UUID("11111111-1111-4111-8111-111111111111"),
        modelo="130",
        filing_year=2026,
        period=PublicPeriod.from_period(Period.from_year_and_code(2026, "1T")),
        registry_revision_id="revision-1",
        completed=False,
        stopped_at_stage=QuickfileStage.CREATE,
        readiness=QuickfileReadinessSummary(
            ready=False,
            profile_ready=False,
            registry_ready=True,
            binding_ready=True,
            ledger_preflight_required=False,
            ledger_ready=None,
            missing_profile_fact_count=1,
            missing_binding_count=0,
            ledger_issue_count=0,
        ),
        work_unit_id=None,
        calculation_revision_id=None,
        verification_report=None,
        export=None,
        stages=(
            QuickfileStageSnapshot(
                stage=QuickfileStage.READINESS,
                status=QuickfileStageStatus.WARNING,
                message="profile is not yet source-ready; caller-supplied inputs may still satisfy calculate",
                facts={"ready": False, "profile_ready": False, "binding_ready": True, "missing_bindings": 0},
            ),
            QuickfileStageSnapshot(
                stage=QuickfileStage.CREATE,
                status=QuickfileStageStatus.REFUSED,
                error=QuickfileStageError(code=error.code, message_key=error.message_key),
            ),
            QuickfileStageSnapshot(stage=QuickfileStage.CALCULATE, status=QuickfileStageStatus.SKIPPED),
            QuickfileStageSnapshot(stage=QuickfileStage.VERIFY, status=QuickfileStageStatus.SKIPPED),
            QuickfileStageSnapshot(stage=QuickfileStage.EXPORT, status=QuickfileStageStatus.SKIPPED),
        ),
        write_count=0,
        effect=OperationEffect.NONE,
    )


def test_quickfile_stage_payload_refuses_unknown_stage_and_status() -> None:
    with pytest.raises(ValidationError):
        QuickfileStageOutcomePayload(stage="bogus", status=QuickfileStageStatus.OK)

    with pytest.raises(ValidationError):
        QuickfileStageOutcomePayload(stage=QuickfileStage.VERIFY, status="bogus")


def test_quickfile_stage_payload_serialises_enums_as_strings() -> None:
    row = QuickfileStageOutcomePayload(stage=QuickfileStage.VERIFY, status=QuickfileStageStatus.REFUSED)
    assert row.model_dump(mode="json")["stage"] == "verify"
    assert row.model_dump(mode="json")["status"] == "refused"


def test_quickfile_result_payload_refuses_unknown_stopped_stage() -> None:
    with pytest.raises(ValidationError):
        QuickfileResultPayload(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            registry_revision_id="revision-1",
            completed=False,
            stopped_at_stage="bogus",
            stages=(),
        )


def test_quickfile_payload_preserves_readiness_summary_and_ordered_stages() -> None:
    payload = QuickfileResultPayload.from_projection(_stopped_projection())

    assert payload.completed is False
    assert payload.stopped_at_stage is QuickfileStage.CREATE
    assert payload.readiness == QuickfileReadinessSummaryPayload(
        ready=False,
        profile_ready=False,
        registry_ready=True,
        binding_ready=True,
        ledger_preflight_required=False,
        ledger_ready=None,
        missing_profile_fact_count=1,
        missing_binding_count=0,
        ledger_issue_count=0,
    )
    document = payload.model_dump(mode="json")
    assert [row["stage"] for row in document["stages"]] == [
        "readiness",
        "create",
        "calculate",
        "verify",
        "export",
    ]
    assert document["stages"][0]["context"] == {}


def test_stage_notice_uses_declared_error_and_never_accepts_raw_cli_command_prose() -> None:
    reason = "--binding not-a-declared-binding is unknown. Use `aeat app modelo bindings list 115` to list them."
    with pytest.raises(ValidationError, match="raw aeat command prose"):
        Notice(severity=NoticeSeverity.WARNING, code="quickfile.stage.calculate", message=reason)

    stage = _stopped_projection().stages[1]
    notice = _stage_notice(stage)
    Notice.model_validate_json(json.dumps(notice.model_dump(mode="json")))
    assert "aeat" not in notice.message.lower()
    assert notice.context is not None
    assert notice.context["error_code"] == "REFUSED_MODELO_PROFILE_READINESS"
    assert notice.action is None
