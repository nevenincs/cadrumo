"""Exact-profile CLI bridge and route for invoice withholding aggregation."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.service import PerModeloAggregationCommand, PerModeloAggregationContributor
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....application.modelo.invoice_withholding_capture_operation import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
    MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE,
    ModeloInvoiceWithholdingCaptureProjection,
    ModeloInvoiceWithholdingCaptureRequest,
)
from ....application.operations.public_period import PublicPeriod
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.aggregation import BindingSourceKind
from ....core.hashing import content_hash_hex
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from .. import _modelo_aggregate_cli as aggregate_cli
from .. import runtime_modelo_invoice_withholding as bridge
from .._modelo_payloads import ModeloAggregateResult
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OPERATION_ID = "b" * 64
_PERIOD = Period.from_year_and_code(2025, "1T")
_PUBLIC_PERIOD = PublicPeriod.from_period(_PERIOD)


def _evidence() -> InvoiceWithholdingEvidenceRequest:
    return InvoiceWithholdingEvidenceRequest(
        invoice_id="a" * 64,
        income_kind=WithholdingIncomeKind.PROFESSIONAL,
        scheme="actividades_profesionales",
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        allocation_id="allocation-test",
        allocated_base=Decimal("1000.00"),
        allocated_withholding=Decimal("150.00"),
        allocated_settlement=Decimal("1060.00"),
        idempotency_key="capture-test",
    )


def _command() -> PerModeloAggregationCommand:
    return PerModeloAggregationCommand(modelo="111", period=_PERIOD)


def _window() -> SimpleNamespace:
    return SimpleNamespace(
        baseline=SimpleNamespace(
            scope_token=content_hash_hex({"scope": "invoice withholding bridge test"}),
            generation_id="a" * 64,
        ),
        generation=1,
        generation_audit=None,
    )


def _projection(
    *,
    outcome: str = "captured",
    profile_id: UUID = _PROFILE,
    refusal_reason: str | None = None,
) -> ModeloInvoiceWithholdingCaptureProjection:
    captured = outcome == "captured"
    return ModeloInvoiceWithholdingCaptureProjection.model_construct(
        outcome=outcome,
        profile_id=profile_id,
        modelo="111",
        period=_PUBLIC_PERIOD,
        provider=PerModeloAggregationContributor.RETENCIONES if captured else None,
        observation_count=1 if captured else None,
        source_kinds=(BindingSourceKind.PAYABLE_INVOICE,) if captured else None,
        result_row_count=1 if captured else None,
        withholding_window=_window() if captured else None,
        refusal_reason=refusal_reason,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[ModeloInvoiceWithholdingCaptureProjection],
) -> list[tuple[object, dict[str, object]]]:
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "bound_profile_client", lambda _ctx: client)
    submitted: list[tuple[object, dict[str, object]]] = []

    def submit(submitted_client: object, request: object, **kwargs: object):
        assert submitted_client is client
        submitted.append((request, cast(dict[str, object], kwargs)))
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted


def _read():
    return bridge.aggregate_modelo_with_received_invoice_retencion(
        cast(typer.Context, cast(object, None)),
        command=_command(),
        evidence=_evidence(),
    )


def test_bridge_submits_the_command_to_its_bound_profile_and_accepts_idempotent_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=_projection(),
        effect=OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
    )
    submitted = _bind(monkeypatch, completion)

    read = _read()

    assert read.completion.operation_id == _OPERATION_ID
    assert read.projection == completion.projection
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == ModeloInvoiceWithholdingCaptureRequest.from_inputs(
        profile_id=_PROFILE,
        command=_command(),
        evidence=_evidence(),
    )
    assert options["definition_id"] == MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is ModeloInvoiceWithholdingCaptureProjection
    assert options["request_version"] == options["result_version"] == 1
    assert options["allow_refusal_detail"] is True


def test_bridge_renders_only_a_correlated_registered_domain_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusal_reason = "no_retencion_declared"
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(outcome="refused", refusal_reason=refusal_reason),
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.REFUSED,
            refusal_code=MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE,
        ),
    )

    with pytest.raises(typer.BadParameter, match=refusal_reason):
        _read()


@pytest.mark.parametrize("mismatch", ["profile", "period", "terminal", "refusal_code", "effect"])
def test_bridge_rejects_a_projection_or_receipt_that_disagrees_with_the_capture(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _projection(profile_id=_PROFILE)
    condition = OperationTerminalCondition.SUCCEEDED
    effect = OperationEffect.UPDATED
    refusal_code = None
    if mismatch == "profile":
        projection = _projection(profile_id=UUID("33333333-3333-4333-8333-333333333333"))
    elif mismatch == "period":
        projection = _projection().model_copy(update={"period": PublicPeriod(filing_year=2024, code="1T")})
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    elif mismatch == "refusal_code":
        refusal_code = RuntimeRefusalCode.UNAVAILABLE.value
    elif mismatch == "effect":
        effect = OperationEffect.UNKNOWN
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        ),
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _read()

    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_aggregate_cli_invoice_route_uses_worker_summary_without_ambient_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _evidence()
    calls: list[tuple[PerModeloAggregationCommand, InvoiceWithholdingEvidenceRequest]] = []
    rendered: dict[str, object] = {}

    def capture(
        _ctx: object,
        *,
        command: PerModeloAggregationCommand,
        evidence: InvoiceWithholdingEvidenceRequest,
    ):
        calls.append((command, evidence))
        return SimpleNamespace(projection=_projection())

    def no_ambient_authority(*_args: object, **_kwargs: object):
        pytest.fail("invoice evidence route consulted ambient registry authority")

    monkeypatch.setattr(aggregate_cli, "resolve_year_period", no_ambient_authority)
    monkeypatch.setattr(aggregate_cli, "aggregate_modelo_with_received_invoice_retencion", capture)
    monkeypatch.setattr(aggregate_cli, "emit_envelope", lambda _ctx, **kwargs: rendered.update(kwargs))

    aggregate_cli.aggregate_modelo(
        cast(typer.Context, cast(object, None)),
        modelo="111",
        year=2025,
        period="1T",
        received_invoice_retencion=[evidence.model_dump_json()],
    )

    assert len(calls) == 1
    command, submitted_evidence = calls[0]
    assert command.period == _PERIOD
    assert command.retencion_observations == ()
    assert submitted_evidence == evidence
    result = cast(ModeloAggregateResult, rendered["result"])
    assert result.withholding_window.generation == 1
    assert "B12345674" not in result.model_dump_json()
    assert "150.00" not in result.model_dump_json()
    assert rendered["lines"] == [
        "operation\tmodelo.aggregate",
        "modelo\t111",
        f"period\t{_PERIOD.registry_token}",
        "provider\tretenciones",
        "observation_count\t1",
        "source_kinds\tpayable_invoice",
        "result_row_count\t1",
    ]
