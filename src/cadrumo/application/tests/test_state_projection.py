"""Pure application contracts for operator state-projection refusal messages."""

from __future__ import annotations

import pytest

from cadrumo.application.state_projection import (
    ModeloReadinessRequest,
    _registry_readiness_refusal,
    _registry_readiness_revision_mismatch_refusal,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_registry_readiness_refusals_have_no_authored_describe_command() -> None:
    request = ModeloReadinessRequest(modelo="303", revision_id="rev", filing_year=2025)
    quarter = "4T"
    first = _registry_readiness_refusal(request, period_token=quarter, exc=RuntimeError("missing"))
    second = _registry_readiness_revision_mismatch_refusal(
        request,
        period_token=quarter,
        resolved_revision_id="resolved",
    )
    for refusal in (first, second):
        assert "aeat app modelo describe" not in refusal
        assert "revision" in refusal
