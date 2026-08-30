"""Identity contract for the overview-status result payload."""

from __future__ import annotations

import pytest

from ....application.overview.status_report import overview_status_report_from_projection
from ....application.state_projection import (
    OperatorStateProjection,
    ProjectionActiveProfile,
    ProjectionAuthReadiness,
    ProjectionWorkspaceSummary,
)
from ....core.json_contract import strict_round_trip
from .._overview_payloads import OverviewStatusResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_overview_status_result_carries_only_the_operator_label() -> None:
    """The result must not duplicate the envelope identity with a protected id."""
    projection = OperatorStateProjection(
        active_profile=ProjectionActiveProfile(
            profile_id="11111111-1111-4111-8111-111111111111",
            label="operator-manual",
            health_status="ready",
            registered_bucket=True,
            record_present=True,
        ),
        auth=ProjectionAuthReadiness(),
        workspace=ProjectionWorkspaceSummary(transactions=3, work_units=1),
    )

    report = overview_status_report_from_projection(projection)
    payload = strict_round_trip(OverviewStatusResult, report).model_dump(mode="json")

    assert payload["active_profile_name"] == "operator-manual"
    assert "active_profile" not in payload
    assert "11111111-1111-4111-8111-111111111111" not in str(payload)
