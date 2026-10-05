"""Period-scope requirements for the canonical application-owned Modelo reader."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import (
    ADMISSION_ENTRY_ACTIONS,
    ADMISSION_REPLAY_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
)
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    OperationAccessRequest,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..query_read_contracts import ModeloBindingsListRequest, ModeloReadinessOperationRequest
from ..query_read_operation import (
    MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
    _requested_scope,
    require_modelo_query_worker_identity,
    resolve_modelo_query_read_access,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_scope_requires_all_periods_when_a_read_is_not_exact() -> None:
    """A missing-binding or periodless readiness query cannot borrow one period."""
    profile_id = uuid4()
    annual = Period.from_year_and_code(2026, "0A")
    assert _requested_scope(ModeloBindingsListRequest(profile_id=profile_id)) == (frozenset(), True, False)
    assert _requested_scope(ModeloBindingsListRequest(profile_id=profile_id, missing=True)) == (
        frozenset(),
        True,
        True,
    )
    assert _requested_scope(
        ModeloBindingsListRequest(profile_id=profile_id, year=2026, period_code="0A", missing=True)
    ) == (
        frozenset({annual}),
        False,
        False,
    )
    assert _requested_scope(ModeloReadinessOperationRequest(profile_id=profile_id, modelo="303", filing_year=2026)) == (
        frozenset(),
        True,
        True,
    )
    assert _requested_scope(
        ModeloReadinessOperationRequest(
            profile_id=profile_id,
            modelo="303",
            filing_year=2026,
            period=PublicPeriod.from_period(annual),
        )
    ) == (frozenset({annual}), False, False)


def test_query_executor_requires_context_definition_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = uuid4()
    subject_ref = profile_operation_subject(str(profile_id))
    request = OperationRequest[ModeloBindingsListRequest](
        definition_id=MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        payload=ModeloBindingsListRequest(profile_id=profile_id),
    )
    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64,
                    definition_id="modelo.query.other",
                    subject_ref=subject_ref,
                )
            ),
        ),
    )
    monkeypatch.setattr(
        "cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(profile_id)
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        require_modelo_query_worker_identity(MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID, profile_id, request, context)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


_ANNUAL = Period.from_year_and_code(2026, "0A")
_HELD_AUTHORITY = cast(PinnedAuthorityOperation, object())


def _query_context(profile_id: UUID, action: AccessAction, admitted: OperationAccessRequest) -> OperationAccessContext:
    definition_id = MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID
    contract = SimpleNamespace(
        definition_id=definition_id,
        result_schema=SimpleNamespace(schema_id=definition_id + ".result"),
        definition_contract_digest="c" * 64,
    )
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.MCP,
        contract=cast(OperationPublicDefinitionContractV1, cast(object, contract)),
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )


def _query_admission(
    profile_id: UUID,
    *,
    definition_id: str = MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
    action: AccessAction = AccessAction.SUBMIT,
) -> OperationAccessRequest:
    return OperationAccessRequest(
        profile_id=profile_id,
        definition_id=definition_id,
        action=action,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset({_ANNUAL}),
        period_independent=False,
        destination_id=uuid4(),
    )


def _resolve_query(context: OperationAccessContext, profile_id: UUID) -> ResolvedOperationAccess:
    return resolve_modelo_query_read_access(
        OperationRequest[BaseModel](
            definition_id=MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=ModeloBindingsListRequest(profile_id=profile_id),
        ),
        context,
        definition_id=MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
        payload_type=ModeloBindingsListRequest,
        result_category=DisclosureCategory.TAX_VALUES,
    )


@pytest.mark.parametrize("action", sorted(ADMISSION_REPLAY_ACTIONS))
def test_query_replay_from_a_fresh_session_keeps_the_admitted_scope_whatever_its_origin(action: AccessAction) -> None:
    """A later session has a new destination and frontend; profile, definition and SUBMIT still bind."""
    profile_id = uuid4()
    fresh = _query_context(profile_id, action, _query_admission(profile_id))
    assert fresh.admitted_request is not None and fresh.admitted_request.destination_id != fresh.destination_id

    resolved = _resolve_query(fresh, profile_id)

    assert resolved.request.periods == frozenset({_ANNUAL}) and not resolved.request.period_independent
    assert resolved.request.destination_id == fresh.destination_id
    assert resolved.request.frontend is OperationFrontendProjection.MCP
    assert all(item.destination_id == fresh.destination_id for item in resolved.policy.disclosures)
    for foreign in (
        _query_admission(uuid4()),
        _query_admission(profile_id, definition_id="modelo.query.other"),
        _query_admission(profile_id, action=AccessAction.START),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            _resolve_query(replace(fresh, admitted_request=foreign, authority_operation=_HELD_AUTHORITY), profile_id)
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize("action", sorted(ADMISSION_ENTRY_ACTIONS))
def test_query_entry_actions_need_held_authority_and_resolve_the_requested_scope(action: AccessAction) -> None:
    profile_id = uuid4()
    context = _query_context(profile_id, action, _query_admission(profile_id))

    with pytest.raises(ProfileAccessRefusedError) as refused:
        _resolve_query(context, profile_id)

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    resolved = _resolve_query(replace(context, authority_operation=_HELD_AUTHORITY), profile_id)
    assert resolved.request.periods == frozenset() and resolved.request.period_independent
