"""Exact-profile runtime bridge and CLI routing for modelo aggregation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.aggregation.ledger_payment_withholding import LedgerPaymentWithholdingEvidenceRequest
from ....application.aggregation.service import PerModeloAggregationCommand, PerModeloAggregationContributor
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....application.modelo.aggregate_operation import (
    MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE,
    MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
    ModeloAggregateOperationRequest,
    ModeloAggregateProjection,
    ModeloAggregateWindow,
    ModeloAggregateWindowBaseline,
)
from ....application.operations.public_period import PublicPeriod
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.aggregation import BindingSourceKind, RetencionScheme
from ....core.hashing import content_hash_hex
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.withholding_bindings import WithholdingClaveBreakdown
from .. import _modelo_aggregate_cli as aggregate_cli
from .. import runtime_modelo_aggregate as bridge
from .._modelo_payloads import ModeloAggregateResult
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("35353535-3535-4353-8353-353535353535")
_OPERATION_ID = "d" * 64
_PERIOD = Period.from_year_and_code(2025, "1T")
_PUBLIC_PERIOD = PublicPeriod.from_period(_PERIOD)


def _command(*, modelo: str = "111") -> PerModeloAggregationCommand:
    return PerModeloAggregationCommand(modelo=modelo, period=_PERIOD)


def _window() -> ModeloAggregateWindow:
    return ModeloAggregateWindow(
        baseline=ModeloAggregateWindowBaseline(
            scope_token=content_hash_hex({"scope": "modelo aggregate bridge test"}),
            generation_id="a" * 64,
        ),
        generation=1,
    )


def _projection(
    *,
    outcome: str = "aggregated",
    profile_id: UUID = _PROFILE,
    modelo: str = "111",
    period: PublicPeriod = _PUBLIC_PERIOD,
    refusal_reason: str | None = None,
) -> ModeloAggregateProjection:
    if outcome == "refused":
        return ModeloAggregateProjection(
            outcome="refused",
            profile_id=profile_id,
            modelo=modelo,
            period=period,
            refusal_reason=refusal_reason,
        )
    return ModeloAggregateProjection(
        outcome="aggregated",
        profile_id=profile_id,
        modelo=modelo,
        period=period,
        provider=PerModeloAggregationContributor.RETENCIONES,
        observation_count=1,
        source_kinds=(BindingSourceKind.PAYABLE_INVOICE,),
        result_row_count=1,
        clave_breakdown=(),
        withholding_window=_window() if modelo in {"111", "115", "123"} else None,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[ModeloAggregateProjection],
) -> list[tuple[object, dict[str, object]]]:
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "bound_profile_client", lambda _ctx: client)
    submitted: list[tuple[object, dict[str, object]]] = []

    def submit(submitted_client: object, request: object, **kwargs: object):
        assert submitted_client is client
        submitted.append((request, kwargs))
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted


def _run(*, ledger_payment: LedgerPaymentWithholdingEvidenceRequest | None = None):
    return bridge.run_modelo_aggregate(
        cast(typer.Context, cast(object, None)),
        command=_command(),
        ledger_payment=ledger_payment,
    )


def _ledger_payment() -> LedgerPaymentWithholdingEvidenceRequest:
    return LedgerPaymentWithholdingEvidenceRequest.model_validate(
        {
            "transaction_id": "a" * 64,
            "income_kind": WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
            "scheme": RetencionScheme("intereses"),
            "recipient_tax_status": WithholdingRecipientTaxStatus.RESIDENT,
            "recipient_tax_regime": WithholdingRecipientTaxRegime.IRPF,
            "payment_event_id": "payment-test",
            "allocation_id": "allocation-test",
            "gross_base": Decimal("100.00"),
            "withholding_amount": Decimal("15.00"),
            "net_settlement": Decimal("85.00"),
            "idempotency_key": "capture-test",
            "perceptor_nif": "12345678A",
            "perceptor_name": "Perceptor Sintetico",
            "exigibility_event_id": "exigibility-test",
            "exigibility_occurred_on": date(2025, 2, 1),
        }
    )


def test_bridge_submits_exact_profile_command_and_correlates_read_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=_projection(),
        effect=OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
    )
    submitted = _bind(monkeypatch, completion)

    result = _run()

    assert result == completion.projection
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == ModeloAggregateOperationRequest.from_inputs(profile_id=_PROFILE, command=_command())
    assert options["definition_id"] == MODELO_AGGREGATE_OPERATION_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is ModeloAggregateProjection
    assert options["request_version"] == options["result_version"] == 1
    assert options["allow_refusal_detail"] is True


@pytest.mark.parametrize("effect", [OperationEffect.UPDATED, OperationEffect.NONE])
def test_bridge_accepts_only_a_correlated_ledger_capture_effect(
    monkeypatch: pytest.MonkeyPatch,
    effect: OperationEffect,
) -> None:
    ledger_payment = _ledger_payment()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=_projection(),
        effect=effect,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
    )
    submitted = _bind(monkeypatch, completion)

    _run(ledger_payment=ledger_payment)

    request, _ = submitted[0]
    assert isinstance(request, ModeloAggregateOperationRequest)
    assert request.profile_id == _PROFILE
    assert request.command.to_domain() == _command()
    assert request.ledger_payment is not None
    assert request.ledger_payment.to_domain() == ledger_payment


def test_bridge_renders_only_a_correlated_registered_domain_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reason = "ledger_payment_period_mismatch"
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(outcome="refused", refusal_reason=reason),
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.REFUSED,
            refusal_code=MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE,
        ),
    )

    with pytest.raises(typer.BadParameter, match=reason):
        _run()


@pytest.mark.parametrize("mismatch", ["profile", "modelo", "period", "breakdown", "terminal", "refusal_code", "effect"])
def test_bridge_rejects_a_projection_or_receipt_that_disagrees_with_its_request(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _projection()
    condition = OperationTerminalCondition.SUCCEEDED
    effect = OperationEffect.NONE
    refusal_code = None
    if mismatch == "profile":
        projection = _projection(profile_id=UUID("46464646-4646-4464-8464-464646464646"))
    elif mismatch == "modelo":
        projection = _projection(modelo="115")
    elif mismatch == "period":
        projection = _projection(period=PublicPeriod(filing_year=2024, code="1T"))
    elif mismatch == "breakdown":
        breakdown = WithholdingClaveBreakdown.model_construct(
            clave="A", percepcion_count=1, percibido_total=Decimal("100.00"), retencion_total=Decimal("15.00")
        )
        projection = projection.model_copy(update={"clave_breakdown": (breakdown,)})
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    elif mismatch == "refusal_code":
        refusal_code = "unexpected_refusal"
    elif mismatch == "effect":
        effect = OperationEffect.UPDATED
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
        _run()

    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_cli_routes_regular_aggregate_through_the_profile_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection()
    submitted: list[tuple[PerModeloAggregationCommand, LedgerPaymentWithholdingEvidenceRequest | None]] = []
    rendered: dict[str, object] = {}

    def run(
        _ctx: object,
        *,
        command: PerModeloAggregationCommand,
        ledger_payment: LedgerPaymentWithholdingEvidenceRequest | None = None,
    ) -> ModeloAggregateProjection:
        submitted.append((command, ledger_payment))
        return projection

    monkeypatch.setattr(aggregate_cli, "run_modelo_aggregate", run)
    monkeypatch.setattr(aggregate_cli, "emit_envelope", lambda _ctx, **kwargs: rendered.update(kwargs))

    aggregate_cli.aggregate_modelo(cast(typer.Context, cast(object, None)), modelo="111", year=2025, period="1T")

    assert len(submitted) == 1
    command, ledger_payment = submitted[0]
    assert command.period == _PERIOD
    assert command.retencion_observations == ()
    assert ledger_payment is None
    result = cast(ModeloAggregateResult, rendered["result"])
    assert result.withholding_window is not None
    assert result.withholding_window.generation == 1
    assert rendered["lines"] == [
        "operation\tmodelo.aggregate",
        "modelo\t111",
        f"period\t{_PERIOD.registry_token}",
        "provider\tretenciones",
        "observation_count\t1",
        "source_kinds\tpayable_invoice",
        "result_row_count\t1",
    ]


def test_cli_refuses_mixed_ledger_capture_inputs_before_submitting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        aggregate_cli,
        "run_modelo_aggregate",
        lambda *_args, **_kwargs: pytest.fail("mixed evidence reached the profile operation"),
    )

    with pytest.raises(typer.BadParameter):
        aggregate_cli.aggregate_modelo(
            cast(typer.Context, cast(object, None)),
            modelo="111",
            year=2025,
            period="1T",
            counterpart_observation=["not-json"],
            ledger_payment_withholding=["not-json"],
        )


def test_cli_refuses_retired_withholding_observation_transport_before_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        aggregate_cli,
        "run_modelo_aggregate",
        lambda *_args, **_kwargs: pytest.fail("retired observation transport reached the profile operation"),
    )

    with pytest.raises(typer.BadParameter, match="--withholding-observation is not accepted for Modelo 100"):
        aggregate_cli.aggregate_modelo(
            cast(typer.Context, cast(object, None)),
            modelo="100",
            year=2025,
            period="0A",
            withholding_observation=["not-json"],
        )
