"""TUI lifecycle submission keeps ordinary-M303 evidence typed and explicit."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from ......application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationAdmission,
)
from ......application.modelo.operation_definitions import (
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV1,
    ModeloWorkCalculateRequest,
)
from ......application.operations.models import OperationRequest
from ...lifecycle import ModeloLifecycleActionUnavailableError, ModeloWorkspaceLifecycleDoor

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ATTACHMENT_ID = "a" * 64


def _door() -> ModeloWorkspaceLifecycleDoor:
    """Build a door whose private submit seam is replaced by each test."""
    return ModeloWorkspaceLifecycleDoor(services=cast(Any, object()), work_unit_id="work-unit-303")


@pytest.mark.asyncio
async def test_calculate_passes_the_typed_ordinary_m303_evidence_without_coercing_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both false values and the admitted reference reach the existing request unchanged."""
    captured: list[OperationRequest[ModeloWorkCalculateRequest]] = []
    expected = object()

    async def capture_submit(
        _self: ModeloWorkspaceLifecycleDoor,
        request: OperationRequest[ModeloWorkCalculateRequest],
    ) -> object:
        captured.append(request)
        return expected

    monkeypatch.setattr(ModeloWorkspaceLifecycleDoor, "_submit", capture_submit)
    evidence = ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        m303_exonerado_390_attachment_id=_ATTACHMENT_ID,
        m303_exonerado_390_sha256=_ATTACHMENT_ID,
    )

    result = await _door().calculate(ordinary_m303_filing_evidence=evidence)

    assert result is expected
    payload = captured[0].payload
    assert payload.ordinary_m303_filing_evidence == evidence
    assert payload.ordinary_m303_filing_evidence.joint_return_elected is False
    assert payload.ordinary_m303_filing_evidence.annual_volume_nonzero is False


@pytest.mark.asyncio
async def test_calculate_leaves_the_optional_m303_subrequest_absent_for_existing_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-M303 caller retains the pre-evidence request shape."""
    captured: list[OperationRequest[ModeloWorkCalculateRequest]] = []

    async def capture_submit(
        _self: ModeloWorkspaceLifecycleDoor,
        request: OperationRequest[ModeloWorkCalculateRequest],
    ) -> object:
        captured.append(request)
        return object()

    monkeypatch.setattr(ModeloWorkspaceLifecycleDoor, "_submit", capture_submit)

    await _door().calculate()

    payload = captured[0].payload
    assert payload.ordinary_m303_filing_evidence is None
    assert "ordinary_m303_filing_evidence" not in payload.model_fields_set


@pytest.mark.asyncio
async def test_attestation_admission_exposes_only_its_secure_coordinates_to_calculation() -> None:
    """The TUI lifecycle door uses the injected application admission result, never raw evidence bytes."""
    admission = M303Exonerado390ApplicabilityAttestationAdmission(
        attachment_id=_ATTACHMENT_ID,
        sha256=_ATTACHMENT_ID,
    )
    door = ModeloWorkspaceLifecycleDoor(
        services=cast(Any, object()),
        work_unit_id="work-unit-303",
        m303_exonerado_390_attestation_admission=lambda _observed_at: admission,
    )

    evidence = await door.author_ordinary_m303_filing_evidence(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        observed_at=datetime(2026, 9, 22, tzinfo=UTC),
    )

    assert evidence.joint_return_elected is False
    assert evidence.annual_volume_nonzero is False
    assert evidence.m303_exonerado_390_attachment_id == _ATTACHMENT_ID
    assert evidence.m303_exonerado_390_sha256 == _ATTACHMENT_ID


@pytest.mark.asyncio
async def test_attestation_admission_without_an_injected_door_refuses_instead_of_calculating() -> None:
    """A lifecycle door that cannot admit evidence reports that, never a substitute reference."""
    door = _door()

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        await door.author_ordinary_m303_filing_evidence(
            joint_return_elected=False,
            annual_volume_nonzero=False,
            observed_at=datetime(2026, 9, 22, tzinfo=UTC),
        )

    assert raised.value.translated_message == "tui.modelo.m303_evidence.admission_unavailable"
