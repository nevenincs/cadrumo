"""Registered verify reads keep exact profile scope and validate CLI frames."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.live.verify import VerifySurface
from ....application.live.verify_read_operation import (
    VERIFY_LATEST_DEFINITION_ID,
    VERIFY_LIST_DEFINITION_ID,
    VERIFY_VIEW_DEFINITION_ID,
    VerifyLatestPublicResultV1,
    VerifyLatestRequest,
    VerifyListPublicResultV1,
    VerifyListRequest,
    VerifyObservationPublicV1,
    VerifyObservationSummaryPublicV1,
    VerifyViewRequest,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.identity_check_verdict import IdentityCheckVerdict
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_profile_operation as profile_operation
from .. import runtime_verify_read as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_FOREIGN_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 9, 29, 10, 30, tzinfo=UTC)
_NIF = "B12345674"
_OBSERVATION_ID = "c" * 64


def _summary() -> VerifyObservationSummaryPublicV1:
    return VerifyObservationSummaryPublicV1(
        observation_id=_OBSERVATION_ID,
        surface=VerifySurface.NIF_IVA,
        nif=_NIF,
        verdict=IdentityCheckVerdict.VALID,
        expected=IdentityCheckVerdict.VALID,
        matched_expectation=True,
        checked_at=_NOW,
    )


def _list_projection(*, bucket_id: UUID = _PROFILE) -> VerifyListPublicResultV1:
    return VerifyListPublicResultV1(bucket_id=str(bucket_id), count=1, rows=(_summary(),))


def _view_projection(*, bucket_id: UUID = _PROFILE) -> VerifyObservationPublicV1:
    return VerifyObservationPublicV1(**_summary().model_dump(), bucket_id=str(bucket_id))


def _latest_projection(
    *, bucket_id: UUID = _PROFILE, observation_id: str | None = _OBSERVATION_ID
) -> VerifyLatestPublicResultV1:
    return VerifyLatestPublicResultV1(
        bucket_id=str(bucket_id),
        observation_id=observation_id,
        surface=VerifySurface.NIF_IVA,
        nif=_NIF,
        verdict=IdentityCheckVerdict.VALID if observation_id is not None else None,
        expected=IdentityCheckVerdict.VALID if observation_id is not None else None,
        matched_expectation=True if observation_id is not None else None,
        checked_at=_NOW if observation_id is not None else None,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projections: Mapping[str, BaseModel],
    *,
    effect: OperationEffect = OperationEffect.NONE,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[BaseModel, dict[str, object]]], list[UUID]]:
    bound_profiles: list[UUID] = []
    client = SimpleNamespace(profile_id=_PROFILE)

    def require_client(_ctx: object) -> object:
        bound_profiles.append(client.profile_id)
        return client

    monkeypatch.setattr(bridge, "bound_profile_client", require_client)
    submitted: list[tuple[BaseModel, dict[str, object]]] = []

    def submit(
        submitted_client: object, request: BaseModel, **kwargs: object
    ) -> RegisteredOperationCompletion[BaseModel]:
        assert submitted_client is client
        submitted.append((request, kwargs))
        definition_id = cast(str, kwargs["definition_id"])
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projections[definition_id],
            effect=effect,
            terminal_condition=terminal_condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(profile_operation, "run_registered_operation", submit)
    return submitted, bound_profiles


def _context() -> typer.Context:
    return cast(typer.Context, cast(object, None))


def test_reads_submit_on_bound_profile_with_registered_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    projections = {
        VERIFY_LIST_DEFINITION_ID: _list_projection(),
        VERIFY_VIEW_DEFINITION_ID: _view_projection(),
        VERIFY_LATEST_DEFINITION_ID: _latest_projection(observation_id=None),
    }
    submitted, bound_profiles = _bind(monkeypatch, projections)

    listed = bridge.read_verify_list_for_cli(_context(), surface=VerifySurface.NIF_IVA, nif=_NIF)
    viewed = bridge.read_verify_view_for_cli(_context(), observation_id="c" * 12)
    latest = bridge.read_verify_latest_for_cli(_context(), surface=VerifySurface.NIF_IVA, nif=_NIF)

    assert bound_profiles == [_PROFILE, _PROFILE, _PROFILE]
    assert listed.completion.operation_id == viewed.completion.operation_id == latest.completion.operation_id
    assert [request for request, _ in submitted] == [
        VerifyListRequest(profile_id=_PROFILE, surface=VerifySurface.NIF_IVA, nif=_NIF),
        VerifyViewRequest(profile_id=_PROFILE, observation_id="c" * 12),
        VerifyLatestRequest(profile_id=_PROFILE, surface=VerifySurface.NIF_IVA, nif=_NIF),
    ]
    for (_request, options), definition_id, result_type in zip(
        submitted,
        (VERIFY_LIST_DEFINITION_ID, VERIFY_VIEW_DEFINITION_ID, VERIFY_LATEST_DEFINITION_ID),
        (VerifyListPublicResultV1, VerifyObservationPublicV1, VerifyLatestPublicResultV1),
        strict=True,
    ):
        assert options["definition_id"] == definition_id
        assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert options["result_type"] is result_type
        assert options["request_version"] == options["result_version"] == 1
    assert latest.projection.observation_id is None
    assert latest.projection.checked_at is None


@pytest.mark.parametrize(
    ("definition_id", "read_name", "projection_update", "effect"),
    [
        (VERIFY_LIST_DEFINITION_ID, "list", {"bucket_id": str(_FOREIGN_PROFILE)}, OperationEffect.NONE),
        (VERIFY_VIEW_DEFINITION_ID, "view", {"bucket_id": str(_FOREIGN_PROFILE)}, OperationEffect.NONE),
        (VERIFY_LATEST_DEFINITION_ID, "latest", {"bucket_id": str(_FOREIGN_PROFILE)}, OperationEffect.NONE),
        (VERIFY_LIST_DEFINITION_ID, "list", {}, OperationEffect.UPDATED),
    ],
)
def test_scope_or_receipt_mismatch_is_a_correlated_invalid_frame(
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
    read_name: str,
    projection_update: dict[str, object],
    effect: OperationEffect,
) -> None:
    projections: dict[str, BaseModel] = {
        VERIFY_LIST_DEFINITION_ID: _list_projection(),
        VERIFY_VIEW_DEFINITION_ID: _view_projection(),
        VERIFY_LATEST_DEFINITION_ID: _latest_projection(),
    }
    projections[definition_id] = projections[definition_id].model_copy(update=projection_update)
    _bind(monkeypatch, projections, effect=effect)

    with pytest.raises(CliRefusedBoundaryError) as error:
        if read_name == "list":
            bridge.read_verify_list_for_cli(_context(), surface=VerifySurface.NIF_IVA, nif=_NIF)
        elif read_name == "view":
            bridge.read_verify_view_for_cli(_context(), observation_id="c" * 12)
        else:
            bridge.read_verify_latest_for_cli(_context(), surface=VerifySurface.NIF_IVA, nif=_NIF)

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_cli_bridge_rejects_a_list_row_outside_its_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _list_projection().model_copy(
        update={"rows": (_summary().model_copy(update={"surface": VerifySurface.TGVI}),)}
    )
    _bind(monkeypatch, {VERIFY_LIST_DEFINITION_ID: projection})

    with pytest.raises(CliRefusedBoundaryError) as error:
        bridge.read_verify_list_for_cli(_context(), surface=VerifySurface.NIF_IVA, nif=_NIF)

    assert error.value.context is not None
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_cli_bridge_rejects_latest_row_outside_its_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _latest_projection().model_copy(update={"nif": "C12345678"})
    _bind(monkeypatch, {VERIFY_LATEST_DEFINITION_ID: projection})

    with pytest.raises(CliRefusedBoundaryError) as error:
        bridge.read_verify_latest_for_cli(_context(), surface=VerifySurface.NIF_IVA, nif=_NIF)

    assert error.value.context is not None
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
