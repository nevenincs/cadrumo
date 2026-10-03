"""The maritime preview bridge submits a closed request to one bound profile."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.modelo.maritime_preview_operation import (
    MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
    MaritimePreviewCasillaValue,
    MaritimePreviewObservation,
    ModeloMaritimePreviewProjection,
    ModeloMaritimePreviewRequest,
)
from ....application.operations.models import OperationId
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition
from .. import runtime_modelo_maritime_preview as runtime
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("12345678-1234-4234-8234-123456789abc")
_FOREIGN_PROFILE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _ctx() -> typer.Context:
    return cast(typer.Context, SimpleNamespace())


def _projection(*, profile_id: UUID = _PROFILE_ID) -> ModeloMaritimePreviewProjection:
    observation = MaritimePreviewObservation(
        casilla_id="0525",
        value="10000.00",
        formula_id="renta-maritime-exempt-income-0525",
        legal_refs=("ley-35-2006:art-7",),
        source_refs=("boe-lirpf-statutory-facts",),
    )
    return ModeloMaritimePreviewProjection(
        profile_id=profile_id,
        worker_class="trabajador_del_mar",
        vessel_flag="foreign",
        waters_type=None,
        vessel_registry=None,
        retmar_registered=False,
        retmar_mandatory_filing=False,
        retmar_warning=None,
        observations=(observation,),
        casilla_values=(MaritimePreviewCasillaValue(casilla_id="0525", value="10000.00"),),
    )


def _install_completion(
    monkeypatch: pytest.MonkeyPatch,
    projection: ModeloMaritimePreviewProjection,
    *,
    effect: OperationEffect = OperationEffect.NONE,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> dict[str, object]:
    client = cast(RuntimeFrontendClient, cast(object, SimpleNamespace(profile_id=_PROFILE_ID)))
    captured: dict[str, object] = {}
    monkeypatch.setattr(runtime, "bound_profile_client", lambda _ctx: client)

    def run(
        actual_client: RuntimeFrontendClient,
        request: ModeloMaritimePreviewRequest,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[ModeloMaritimePreviewProjection]:
        captured.update(client=actual_client, request=request, **kwargs)
        return RegisteredOperationCompletion(
            operation_id=cast(OperationId, "a" * 64),
            projection=projection,
            effect=effect,
            terminal_condition=terminal_condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(runtime, "run_registered_operation", run)
    return captured


def test_bridge_submits_canonical_amounts_and_correlates_the_complete_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection()
    captured = _install_completion(monkeypatch, projection)

    result = runtime.preview_modelo_maritime_exemption(
        _ctx(),
        annual_salary=Decimal("36500.00"),
        qualifying_days=100,
        gross_navigation_income=Decimal("30000"),
    )

    request = cast(ModeloMaritimePreviewRequest, captured["request"])
    assert request.profile_id == _PROFILE_ID
    assert request.annual_salary == "36500.00"
    assert request.qualifying_days == 100
    assert request.gross_navigation_income == "30000"
    assert captured["definition_id"] == MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID
    assert captured["subject_ref"] == f"profile:{_PROFILE_ID}"
    assert captured["result_type"] is ModeloMaritimePreviewProjection
    assert captured["request_version"] == captured["result_version"] == 1
    assert captured["timeout"] == 120
    assert result is projection


@pytest.mark.parametrize("mismatch", ["profile", "effect", "terminal", "casilla_values"])
def test_bridge_rejects_projection_or_receipt_mismatches(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.NONE
    terminal = OperationTerminalCondition.SUCCEEDED
    if mismatch == "profile":
        projection = _projection(profile_id=_FOREIGN_PROFILE_ID)
    elif mismatch == "effect":
        effect = OperationEffect.UPDATED
    elif mismatch == "terminal":
        terminal = OperationTerminalCondition.REFUSED
    else:
        projection = projection.model_copy(
            update={"casilla_values": (MaritimePreviewCasillaValue(casilla_id="0526", value="10000.00"),)},
        )
    _install_completion(monkeypatch, projection, effect=effect, terminal_condition=terminal)

    with pytest.raises(CliRefusedBoundaryError) as raised:
        runtime.preview_modelo_maritime_exemption(
            _ctx(),
            annual_salary=None,
            qualifying_days=None,
            gross_navigation_income=None,
        )

    assert raised.value.context is not None
    assert raised.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
