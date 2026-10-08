"""The CLI preparation bridge binds requests to the authenticated profile."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import pytest
import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode
from cadrumo.application.user_profile.censal_operation import (
    CensalFieldIntent,
    CensalOperationRequest,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
)
from cadrumo.application.user_profile.censal_prepare_operation import (
    CENSAL_PREPARE_OPERATION_DEFINITION_ID,
    CensalPrepareFieldProjection,
    CensalPrepareFieldState,
    CensalPrepareOperationProjection,
)
from cadrumo.application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.entrypoints.cli.config import runtime_censal_prepare
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
from cadrumo.entrypoints.cli.registered_operation_contracts import RegisteredOperationCompletion

_PROFILE_ID = UUID("aa000000-0000-4000-8000-0000000000aa")
_FOREIGN_PROFILE_ID = UUID("bb000000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "f" * 64

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _BoundClient:
    profile_id = _PROFILE_ID
    session_id = UUID("cc000000-0000-4000-8000-0000000000cc")
    frontend = OperationFrontendProjection.CLI


def _projection(profile_id: UUID = _PROFILE_ID) -> CensalPrepareOperationProjection:
    request = CensalOperationRequest(
        baseline=CensalProfileBaseline(profile_id=str(profile_id), record_revision=3, content_digest="a" * 64),
        field_intents=tuple(
            CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT) for path in CENSAL_ADOPTABLE_PATHS
        ),
    )
    return CensalPrepareOperationProjection(
        profile_id=profile_id,
        operation_request=request,
        effective_fields=tuple(
            CensalPrepareFieldProjection(path=path, state=CensalPrepareFieldState.UNSET)
            for path in CENSAL_ADOPTABLE_PATHS
        ),
    )


def _install_bridge(monkeypatch: pytest.MonkeyPatch, projection: CensalPrepareOperationProjection):
    client = _BoundClient()
    captured: dict[str, Any] = {}
    monkeypatch.setattr(runtime_censal_prepare, "bound_profile_client", lambda _ctx: client)

    def run_registered_operation(received_client: object, payload: object, **options: object):
        captured.update(client=received_client, payload=payload, options=options)
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        )

    monkeypatch.setattr(runtime_censal_prepare, "run_registered_operation", run_registered_operation)
    return client, captured


def test_prepare_bridge_submits_uuid_profile_and_returns_its_canonical_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection()
    client, captured = _install_bridge(monkeypatch, projection)

    prepared = runtime_censal_prepare.prepare_censal_review(cast(typer.Context, object()))

    assert prepared is projection
    assert captured["client"] is client
    request = captured["payload"]
    assert request.profile_id == client.profile_id
    assert isinstance(request.profile_id, UUID)
    assert prepared.profile_id == client.profile_id
    assert prepared.operation_request.baseline.profile_id == str(client.profile_id)
    assert captured["options"] == {
        "definition_id": CENSAL_PREPARE_OPERATION_DEFINITION_ID,
        "subject_ref": profile_operation_subject(str(client.profile_id)),
        "result_type": CensalPrepareOperationProjection,
        "request_version": 1,
        "result_version": 1,
        "timeout": 60,
    }


def test_prepare_refusal_retains_operation_identity_and_observed_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mismatched = _projection().model_copy(update={"profile_id": _FOREIGN_PROFILE_ID})
    _client, _captured = _install_bridge(monkeypatch, mismatched)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        runtime_censal_prepare.prepare_censal_review(cast(typer.Context, object()))

    assert refused.value.context == {
        "operation_id": _OPERATION_ID,
        "reason": RuntimeRefusalCode.INVALID_FRAME.value,
        "effect": OperationEffect.NONE.value,
        "terminal_condition": OperationTerminalCondition.SUCCEEDED.value,
    }
