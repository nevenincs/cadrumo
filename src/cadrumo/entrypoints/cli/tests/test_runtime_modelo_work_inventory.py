"""CLI work inventory binds one selected profile and preserves bad-result receipts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ....application.modelo.work_inventory_operation import ModeloWorkListProjection, ModeloWorkListRequest
from ....core.operations import OperationEffect
from .. import runtime_modelo_work_inventory as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")


def test_explicit_foreign_bucket_refused_before_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    submissions: list[ModeloWorkListRequest] = []
    monkeypatch.setattr(bridge, "resolve_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        bridge, "require_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE)
    )
    monkeypatch.setattr(
        bridge, "run_registered_operation", lambda _client, request, **_kwargs: submissions.append(request)
    )
    with pytest.raises(RuntimeFrontendRefusedError):
        bridge.read_modelo_work_inventory(
            cast(typer.Context, cast(object, None)), bucket_id=str(_OTHER), include_discarded=False
        )
    assert submissions == []


@pytest.mark.parametrize("effect", [OperationEffect.NONE, OperationEffect.UNKNOWN])
def test_result_correlation_or_receipt_preserving_refusal(
    monkeypatch: pytest.MonkeyPatch, effect: OperationEffect
) -> None:
    requests: list[ModeloWorkListRequest] = []
    projection = ModeloWorkListProjection(profile_id=_PROFILE, include_discarded=False, units=())
    monkeypatch.setattr(bridge, "resolve_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        bridge, "require_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE)
    )

    def submit(_client: object, request: ModeloWorkListRequest, **_kwargs: object):
        requests.append(request)
        return RegisteredOperationCompletion(operation_id="a" * 64, projection=projection, effect=effect)

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    context = cast(typer.Context, cast(object, None))
    if effect is OperationEffect.NONE:
        assert bridge.read_modelo_work_inventory(context, bucket_id=None, include_discarded=False) == ()
    else:
        with pytest.raises(CliRefusedBoundaryError) as refused:
            bridge.read_modelo_work_inventory(context, bucket_id=None, include_discarded=False)
        details = refused.value.context
        assert details is not None
        assert details["operation_id"] == "a" * 64
        assert details["effect"] == OperationEffect.UNKNOWN.value
    assert len(requests) == 1
    assert requests[0].profile_id == _PROFILE
    assert requests[0].include_discarded is False
