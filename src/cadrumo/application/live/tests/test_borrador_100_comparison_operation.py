"""The borrador comparison is a human-only, exact-profile read that releases only a no-effect success.

The comparison itself is exercised over real encrypted storage and a real
calculation in the entrypoint persistence tests; these cases hold the
registered read's own refusals.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.external_constants import OutputLanguage
from ....core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ....domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.registry import OperationRegistry
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import borrador_100_comparison_operation as module
from ..borrador_100_comparison import (
    Borrador100ComparisonCounts,
    Borrador100ComparisonProjection,
    Borrador100ComparisonSources,
    Borrador100ComparisonStatus,
    Borrador100ComparisonWords,
)
from .borrador_100_operation_support import PROFILE_ID, Subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_SETTLED_AT = datetime(2026, 10, 1, 12, tzinfo=UTC)


class _UnreadRepository:
    """A repository the refused read must never reach."""

    bucket_id = str(PROFILE_ID)

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"a refused comparison reached the repository through {name}")


def _ports(subject: Subject, *, profile_id: UUID = PROFILE_ID) -> module.Borrador100ComparisonPorts:
    unread = _UnreadRepository()
    return module.Borrador100ComparisonPorts(
        profile_id=profile_id,
        operation=subject.operation,
        borrador_snapshots=subject.repository,
        sources=Borrador100ComparisonSources(
            bucket_id=str(PROFILE_ID),
            work_units=cast("WorkUnitCatalogueRepositoryProtocol", unread),
            calculations=cast("CalculationRevisionCatalogueRepositoryProtocol", unread),
            verifications=cast("VerificationReportCatalogueRepositoryProtocol", unread),
        ),
    )


def _request(profile_id: UUID = PROFILE_ID) -> OperationRequest[module.Borrador100CompareRequest]:
    return OperationRequest[module.Borrador100CompareRequest](
        definition_id=module.BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=module.Borrador100CompareRequest(
            profile_id=profile_id, filing_year=2025, output_language=OutputLanguage.EN
        ),
    )


def _registry(subject: Subject) -> OperationRegistry:
    definition = module.build_borrador_100_compare_definition(lambda **_: _ports(subject))
    return OperationRegistry(
        definitions=(definition,), public_registrations=(module.build_borrador_100_compare_registration(definition),)
    )


@pytest.fixture
def subject(monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation) -> Subject:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(PROFILE_ID))
    return Subject(authority_operation)


@pytest.mark.asyncio
async def test_ports_for_another_profile_are_refused_before_any_read(subject: Subject) -> None:
    wrong = _ports(subject, profile_id=uuid4())
    request = _request()

    with pytest.raises(ProfileAccessRefusedError):
        await module.Borrador100CompareExecutor(lambda **_: wrong).execute(
            request, subject.context(request.definition_id)
        )
    assert subject.repository.reads == 0
    assert subject.events.effects == [] and subject.operands.values == []


def test_access_is_human_only_and_refuses_another_profile(subject: Subject) -> None:
    registry = _registry(subject)
    contract = registry.lookup_public_contract(module.BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID)
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=subject.operation,
    )
    own = _request()
    resolved = module.resolve_borrador_100_compare_access(
        OperationRequest[BaseModel](definition_id=own.definition_id, subject_ref=own.subject_ref, payload=own.payload),
        context,
    )
    assert resolved.policy.requires_human

    other = _request(uuid4())
    with pytest.raises(ProfileAccessRefusedError) as refused:
        module.resolve_borrador_100_compare_access(
            OperationRequest[BaseModel](
                definition_id=other.definition_id, subject_ref=other.subject_ref, payload=other.payload
            ),
            context,
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_the_projector_releases_only_a_no_effect_success() -> None:
    words = Borrador100ComparisonWords(token=Borrador100ComparisonStatus.NO_CAPTURE.value, words="Nothing imported.")
    result = module.Borrador100CompareExecutionResult(
        projection=Borrador100ComparisonProjection(
            profile_id=PROFILE_ID,
            filing_year=2025,
            language=OutputLanguage.EN,
            status=words,
            stale_reasons=(),
            capture=None,
            refused_captures=0,
            outdated_stored_captures=0,
            calculation=None,
            rows=(),
            counts=Borrador100ComparisonCounts(),
        )
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=module.BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=_SETTLED_AT,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        result_ref="d" * 64,
    )

    assert module.project_borrador_100_compare_result(result, receipt) == result.projection
    for changed in (
        receipt.model_copy(update={"effect": OperationEffect.UNKNOWN}),
        receipt.model_copy(update={"condition": OperationTerminalCondition.FAILED}),
        receipt.model_copy(
            update={"identity": receipt.identity.model_copy(update={"definition_id": "live.borrador.100.read"})}
        ),
    ):
        with pytest.raises(ValueError):
            module.project_borrador_100_compare_result(result, changed)


def test_the_registration_refuses_another_definition(subject: Subject) -> None:
    definition = module.build_borrador_100_compare_definition(lambda **_: _ports(subject))
    with pytest.raises(ValueError):
        module.build_borrador_100_compare_registration(
            definition.model_copy(update={"definition_id": "live.borrador.100.read"})
        )
