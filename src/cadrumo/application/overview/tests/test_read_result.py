"""The overview projector releases only a clean successful no-effect receipt for its own subject."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...operations.models import OperationIdentity, OperationTerminalReceipt
from ..read_payload import OverviewStatusRead
from ..read_projection import OverviewStatusSnapshot
from ..read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadKind, OverviewReadRequest
from ..read_result import OverviewReadResult, project_overview_read_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SETTLED_AT = datetime(2026, 1, 15, 9, 30, tzinfo=UTC)


def _result() -> OverviewReadResult:
    return OverviewReadResult(
        profile_id=_PROFILE_ID,
        request=OverviewReadRequest(
            profile_id=_PROFILE_ID, kind=OverviewReadKind.STATUS, output_language=OutputLanguage.EN
        ),
        payload=OverviewStatusRead(
            report=OverviewStatusSnapshot(
                active_profile_name="synthetic-profile",
                transactions=0,
                invoices=0,
                drafts=0,
                work_units=0,
                discarded_work_units=0,
                calculation_revisions=0,
                unreadable_rows=0,
                filing_obligation_advisories=(),
                unsupported_work_create_modelos=(),
            )
        ),
    )


def _receipt(**changes: object) -> OperationTerminalReceipt:
    fields: dict[str, object] = {
        "identity": OperationIdentity(
            operation_id="a" * 64,
            definition_id=OVERVIEW_READ_DEFINITION_IDS[OverviewReadKind.STATUS],
            subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        ),
        "revision": 1,
        "condition": OperationTerminalCondition.SUCCEEDED,
        "effect": OperationEffect.NONE,
        "settled_at": _SETTLED_AT,
        "result_ref": "result:overview",
    }
    fields.update(changes)
    return OperationTerminalReceipt.model_validate(fields)


def test_a_clean_successful_receipt_releases_the_captured_payload() -> None:
    result = _result()

    projection = project_overview_read_result(result, _receipt())

    assert projection.profile_id == _PROFILE_ID
    assert projection.payload == result.payload


def test_a_successful_receipt_carrying_a_diagnostic_is_not_released() -> None:
    with pytest.raises(ValueError, match="overview read result contradicts its terminal receipt"):
        project_overview_read_result(_result(), _receipt(diagnostic_ref="sha256:0123456789ab"))


def test_a_receipt_for_another_profile_is_not_released() -> None:
    other = OperationIdentity(
        operation_id="a" * 64,
        definition_id=OVERVIEW_READ_DEFINITION_IDS[OverviewReadKind.STATUS],
        subject_ref=profile_operation_subject("6bb00000-0000-4000-8000-0000000000bb"),
    )

    with pytest.raises(ValueError, match="overview read result contradicts its terminal receipt"):
        project_overview_read_result(_result(), _receipt(identity=other))
