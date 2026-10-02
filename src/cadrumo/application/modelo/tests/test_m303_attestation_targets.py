"""The registered M303 attestation has one exact target per request."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from ....core.operations import profile_operation_subject
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationRequest
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import AccessAction, Availability, OperationAccessRequest
from ..m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
    build_modelo_work_m303_attestation_definition,
    build_modelo_work_m303_attestation_registration,
)
from ..metadata_operation_access import compose_modelo_metadata_access
from ..work_lifecycle_ports import WorkLifecyclePorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OBSERVED = datetime(2026, 12, 31, 10, tzinfo=UTC)
_PERIOD = PublicPeriod(filing_year=2026, code="4T")
_UNIT = "a" * 64


def test_explicit_period_has_profile_subject_without_work_unit() -> None:
    request = ModeloWorkM303AttestationRequest(
        profile_id=_PROFILE, period=_PERIOD, observed_at=_OBSERVED, actor="operator"
    )
    assert request.subject_ref == profile_operation_subject(str(_PROFILE))
    assert request.work_unit_id is None


def test_work_unit_has_own_subject_without_period() -> None:
    request = ModeloWorkM303AttestationRequest(
        profile_id=_PROFILE, work_unit_id=_UNIT, observed_at=_OBSERVED, actor="operator"
    )
    assert request.subject_ref == _UNIT
    assert request.period is None


@pytest.mark.parametrize("targets", [{}, {"period": _PERIOD, "work_unit_id": _UNIT}])
def test_ambiguous_or_missing_target_is_refused(targets: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="exactly one target"):
        ModeloWorkM303AttestationRequest.model_validate(
            {"profile_id": _PROFILE, "observed_at": _OBSERVED, "actor": "operator", **targets}
        )


def test_period_receipt_requires_matching_year_and_digest() -> None:
    with pytest.raises(ValidationError, match="identity or period"):
        ModeloWorkM303AttestationPublicResultV2(
            profile_id=_PROFILE,
            work_unit_id=None,
            filing_year=2026,
            period=_PERIOD,
            attachment_id="a" * 64,
            sha256="b" * 64,
        )


@pytest.mark.parametrize("target", ["period", "unit"])
def test_historical_access_uses_sealed_period_without_repository(target: str) -> None:
    def forbidden_repository() -> WorkLifecyclePorts:
        raise AssertionError("historical attestation access must use the sealed period")

    def forbidden_attachment_store(_bucket_id: str) -> AttachmentStoreProtocol:
        raise AssertionError("historical attestation access must not open attachments")

    resolver = compose_modelo_metadata_access(forbidden_repository)
    definition = build_modelo_work_m303_attestation_definition(
        work_lifecycle_ports_factory=forbidden_repository, attachment_store_factory=forbidden_attachment_store
    )
    registration = build_modelo_work_m303_attestation_registration(definition, access_resolver=resolver)
    payload = ModeloWorkM303AttestationRequest.model_validate(
        {
            "profile_id": _PROFILE,
            "observed_at": _OBSERVED,
            "actor": "operator",
            **({"period": _PERIOD} if target == "period" else {"work_unit_id": _UNIT}),
        }
    )
    request = OperationRequest(
        definition_id=MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
        subject_ref=payload.subject_ref,
        payload=payload,
    )
    admitted = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=request.definition_id,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.TUI,
        periods=frozenset({_PERIOD.to_period()}),
        period_independent=False,
        destination_id=uuid4(),
    )
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.TUI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )
    assert resolver(request, context).request.periods == admitted.periods
