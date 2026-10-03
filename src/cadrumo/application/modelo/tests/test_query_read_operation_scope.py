"""Period-scope requirements for the canonical application-owned Modelo reader."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from ....core.operations import profile_operation_subject
from ....core.period import Period
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.public_period import PublicPeriod
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..query_read_contracts import ModeloBindingsListRequest, ModeloReadinessOperationRequest
from ..query_read_operation import (
    MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
    _requested_scope,
    require_modelo_query_worker_identity,
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
