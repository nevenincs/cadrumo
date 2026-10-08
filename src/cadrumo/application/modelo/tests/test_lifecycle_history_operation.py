"""Modelo lifecycle history authorizes its actual period and full-history scope."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..history_ports import ModeloHistoryPorts
from ..lifecycle_history_operation import (
    MODELO_HISTORY_OPERATION_DEFINITION_ID,
    ModeloHistoryOperationProjection,
    ModeloHistoryOperationRequest,
    build_modelo_history_definition,
    build_modelo_history_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _registry() -> OperationRegistry:
    def unopened(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloHistoryPorts:
        raise AssertionError("history access does not open private catalogues")

    definition = build_modelo_history_definition(unopened)
    return OperationRegistry(
        definitions=(definition,), public_registrations=(build_modelo_history_registration(definition),)
    )


def _request(*, year: int | None = None, period: str | None = None) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ModeloHistoryOperationRequest(profile_id=_PROFILE, modelo="303", year=year, period=period),
    )


def test_selected_filing_period_and_full_history_scope(authority_operation: PinnedAuthorityOperation) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(MODELO_HISTORY_OPERATION_DEFINITION_ID)
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )
    selected = resolve_operation_access(registry=registry, request=_request(year=2025, period="1T"), context=context)
    assert selected.request.periods == frozenset({Period.from_year_and_code(2025, "1T")})
    assert not selected.request.period_independent and not selected.policy.requires_all_periods
    full = resolve_operation_access(registry=registry, request=_request(year=2025), context=context)
    assert not full.request.periods and full.request.period_independent and full.policy.requires_all_periods
    for resolved in (selected, full):
        assert AccessAction.COMMIT not in resolved.policy.actions
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(registry=registry, request=_request(), context=replace(context, profile_id=_OTHER))
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_public_history_roundtrips_and_rejects_missing_count() -> None:
    projection = ModeloHistoryOperationProjection(
        profile_id=_PROFILE, modelo="303", year=2025, period="1T", count=0, events=()
    )
    assert ModeloHistoryOperationProjection.model_validate_json(projection.model_dump_json()) == projection
    with pytest.raises(ValidationError):
        ModeloHistoryOperationProjection(profile_id=_PROFILE, modelo="303", count=1, events=())
