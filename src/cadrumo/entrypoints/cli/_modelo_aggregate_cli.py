"""Behavior handlers for modelo aggregation commands.

Core types:
:class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
"""

from __future__ import annotations

import json

import typer
from pydantic import BaseModel, ValidationError

from ...application.aggregation.counterpart import CounterpartObservation
from ...application.aggregation.foreign_assets import ForeignAssetIngestObservation
from ...application.aggregation.invoice_retencion import (
    InvoiceWithholdingDefectsError,
    InvoiceWithholdingEvidenceError,
    InvoiceWithholdingEvidenceRequest,
    build_invoice_withholding_capture,
)
from ...application.aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingEvidenceError,
    LedgerPaymentWithholdingEvidenceRequest,
    build_ledger_payment_withholding_capture,
    resolve_ledger_payment_transaction,
)
from ...application.aggregation.modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from ...application.aggregation.service import (
    CalculationWithholdingRows,
    PerModeloAggregationCommand,
    PerModeloAggregationResult,
    aggregate_per_modelo,
    load_calculation_withholding_rows,
)
from ...application.aggregation.withholding_filing_cadence import (
    PERIODIC_WITHHOLDING_MODELOS,
    load_bucket_withholding_filer_cadence,
)
from ...application.aggregation.withholding_observation_service import (
    WithholdingObservationMutationError,
    WithholdingWindowScope,
)
from ...application.aggregation.withholding_producer import WithholdingProducerError
from ...application.aggregation.withholding_recognition import WithholdingRecognitionError
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.modelo import Modelo
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.withholding_bindings import (
    WithholdingClaveBreakdown,
    aggregate_withholding_by_clave,
)
from ._modelo_behavior_support import resolve_year_period
from ._modelo_payloads import ModeloAggregateResult, WithholdingWindowReadbackPayload
from .common import active_bucket_id_or_refuse, emit_envelope
from .state_projection_support import (
    authority_operation,
    percepcion_observation_ports_factory,
    retencion_observation_ports_factory,
    withholding_observation_service,
)

# Modelo 123 is absent on purpose: its capital withholding is evidenced by the
# paying ledger transaction, and invoice evidence for it is refused outright.
_INVOICE_EVIDENCE_MODELOS = frozenset({Modelo("111").value, Modelo("115").value})
_LEDGER_PAYMENT_WITHHOLDING_MODELOS = frozenset({"111", "123"})
_PERIODIC_WINDOW_MODELOS = frozenset(modelo.value for modelo in PERIODIC_WITHHOLDING_MODELOS)


def _capture_invoice_withholding_into_command(
    ctx: typer.Context,
    command: PerModeloAggregationCommand,
    requests: tuple[InvoiceWithholdingEvidenceRequest, ...],
) -> PerModeloAggregationCommand:
    """Capture one canonical-invoice allocation, then read its active projection.

    The existing aggregate command remains a reporting projection: 111, 115,
    and 123 must never use it as a writable retención transport. Reading the
    active encrypted projection after the shared service succeeds also makes
    omission a genuine no-op rather than an empty set replacement.

    A refusal that names every defect of the invoice's retención is left to
    the registered error boundary, so the operator receives each defect as a
    structured, localized refusal rather than a flattened argument error.
    """
    if requests and command.modelo not in _INVOICE_EVIDENCE_MODELOS:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.aggregate.invoice_retencion_wrong_modelo",
                modelo=command.modelo,
                accepted_modelos=", ".join(sorted(_INVOICE_EVIDENCE_MODELOS)),
            )
        )
    if command.modelo not in _PERIODIC_WINDOW_MODELOS:
        return command
    if len(requests) > 1:
        raise typer.BadParameter(
            "one invoice withholding allocation is accepted per command; submit each allocation explicitly"
        )

    bucket_id = active_bucket_id_or_refuse()
    ports = retencion_observation_ports_factory(ctx)(bucket_id=bucket_id)
    if not requests:
        return command.model_copy(
            update={"retencion_observations": ports.repository.load_observations(command.modelo, command.period)}
        )

    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ...application.invoices.catalogue_lifecycle import resolve_catalogue_invoice

    cadence = load_bucket_withholding_filer_cadence(
        bucket_id=bucket_id,
        filing_year=command.period.filing_year,
        operation=authority_operation(ctx),
    )
    catalogue, catalogue_revision_id = InvoiceCatalogueRepository(bucket_id=bucket_id).load_revisioned()
    try:
        invoice = resolve_catalogue_invoice(catalogue, requests[0].invoice_id)
        capture = build_invoice_withholding_capture(
            invoice,
            catalogue_revision_id=catalogue_revision_id,
            request=requests[0],
            applicable_year=command.period.filing_year,
            cadence=cadence,
        )
    except InvoiceWithholdingDefectsError:
        raise
    except (InvoiceWithholdingEvidenceError, WithholdingRecognitionError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if capture.scope.modelo != command.modelo or capture.scope.period != command.period:
        raise typer.BadParameter("derived recognition period does not match the requested modelo period")

    try:
        from ...application.aggregation.withholding_producer import WithholdingProducer

        WithholdingProducer(service=withholding_observation_service(ctx, bucket_id=bucket_id)).capture(
            capture.command, cadence=cadence
        )
    except (
        WithholdingProducerError,
        WithholdingRecognitionError,
        WithholdingObservationMutationError,
        ValueError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc
    return command.model_copy(
        update={"retencion_observations": ports.repository.load_observations(command.modelo, command.period)}
    )


def _capture_ledger_payment_withholding_into_command(
    ctx: typer.Context,
    command: PerModeloAggregationCommand,
    request: LedgerPaymentWithholdingEvidenceRequest,
) -> PerModeloAggregationCommand:
    """Capture one payroll or capital allocation from its paying ledger transaction, then read the projection.

    The transaction is read between two catalogue revision reads, so the
    capture never rests on a row that changed while it was being read. The
    write goes through the same shared producer as invoice evidence, and the
    active encrypted projection is read back exactly as that path does.
    """
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ...application.aggregation.withholding_producer import WithholdingProducer

    bucket_id = active_bucket_id_or_refuse()
    ports = retencion_observation_ports_factory(ctx)(bucket_id=bucket_id)
    cadence = load_bucket_withholding_filer_cadence(
        bucket_id=bucket_id,
        filing_year=command.period.filing_year,
        operation=authority_operation(ctx),
    )
    transactions = TransactionCatalogueRepository(bucket_id=bucket_id)
    try:
        catalogue_revision_id = transactions.load_revision()
        catalogue = transactions.load_by_ids((request.transaction_id,))
        if catalogue_revision_id is None or transactions.load_revision() != catalogue_revision_id:
            raise LedgerPaymentWithholdingEvidenceError("transaction_catalogue_revision_unavailable")
        capture = build_ledger_payment_withholding_capture(
            resolve_ledger_payment_transaction(catalogue, request.transaction_id),
            catalogue_revision_id=catalogue_revision_id,
            request=request,
            applicable_year=command.period.filing_year,
            cadence=cadence,
        )
    except (LedgerPaymentWithholdingEvidenceError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if capture.scope.modelo != command.modelo or capture.scope.period != command.period:
        raise typer.BadParameter(tr("cli.app.modelo.aggregate.ledger_payment_withholding_period_mismatch"))

    try:
        WithholdingProducer(service=withholding_observation_service(ctx, bucket_id=bucket_id)).capture(
            capture.command, cadence=cadence
        )
    except (
        WithholdingProducerError,
        WithholdingRecognitionError,
        WithholdingObservationMutationError,
        ValueError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc
    return command.model_copy(
        update={"retencion_observations": ports.repository.load_observations(command.modelo, command.period)}
    )


def _refuse_misplaced_ledger_payment_withholding(
    modelo: str,
    *,
    ledger_payment_withholding: list[str] | None,
    received_invoice_retencion: list[str] | None,
) -> None:
    """Refuse a ledger-payment capture outside Modelos 111 and 123 or beside invoice evidence.

    One command writes one allocation from one kind of evidence; letting a
    ledger payment and an invoice share a command would make the resulting
    window depend on which write happened to land first.
    """
    if not ledger_payment_withholding:
        return
    if modelo not in _LEDGER_PAYMENT_WITHHOLDING_MODELOS:
        raise typer.BadParameter(tr("cli.app.modelo.aggregate.ledger_payment_withholding_wrong_modelo", modelo=modelo))
    if received_invoice_retencion:
        raise typer.BadParameter(tr("cli.app.modelo.aggregate.ledger_payment_withholding_exclusive"))
    if len(ledger_payment_withholding) > 1:
        raise typer.BadParameter(tr("cli.app.modelo.aggregate.ledger_payment_withholding_single_allocation"))


def _read_calculation_withholding_rows(
    ctx: typer.Context,
    command: PerModeloAggregationCommand,
) -> CalculationWithholdingRows | None:
    """Read the stored rows an annual withholding summary's calculation reads.

    ``None`` for a periodic window, which its capture path reads back, and for
    a modelo outside the retenciones family, which has no withholding store.
    Every other modelo is an annual summary composed from stored windows, so
    the report reads exactly what its calculation reads instead of an empty
    command.
    """
    if command.modelo in _PERIODIC_WINDOW_MODELOS or not RetencionesAggregationSourceResolver.supports_modelo(
        command.modelo
    ):
        return None
    bucket_id = active_bucket_id_or_refuse()
    operation = authority_operation(ctx)
    return load_calculation_withholding_rows(
        command.modelo,
        command.period,
        operation=operation,
        retencion_ports=retencion_observation_ports_factory(ctx)(bucket_id=bucket_id),
        percepcion_ports=percepcion_observation_ports_factory(ctx)(bucket_id=bucket_id),
        cadence=lambda: load_bucket_withholding_filer_cadence(
            bucket_id=bucket_id,
            filing_year=command.period.filing_year,
            operation=operation,
        ),
    )


def _clave_breakdown(
    calculation_rows: CalculationWithholdingRows | None,
) -> tuple[WithholdingClaveBreakdown, ...]:
    """Project the per-perceptor-clave rows the calculation reads into the per-clave reconciliation aid.

    A pure projection of the rows the percepciones resolver materialises, through
    the helpers its bound facts use, not a recomputation of the calculation
    engine. Empty when the calculation reads no per-perceptor-clave rows.
    """
    if calculation_rows is None or calculation_rows.percepciones is None:
        return ()
    return tuple(aggregate_withholding_by_clave(calculation_rows.percepciones))


def _calculation_rows_absent_notices(
    command: PerModeloAggregationCommand,
    calculation_rows: CalculationWithholdingRows | None,
) -> list[Notice]:
    """Warn once for each source the calculation reads that holds no stored row.

    An empty summary then reads as missing data rather than as a proven zero;
    a stored row whose amounts are zero is counted and raises no warning.
    """
    if calculation_rows is None:
        return []
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="modelo.aggregate.calculation_rows_absent",
            message=tr(
                "cli.app.modelo.aggregate.calculation_rows_absent",
                modelo=command.modelo,
                filing_year=command.period.filing_year,
                period=command.period.registry_token,
                source_family=source_family.value,
            ),
            context={
                "modelo": command.modelo,
                "filing_year": str(command.period.filing_year),
                "period": command.period.registry_token,
                "revision": calculation_rows.revision_id,
                "source_family": source_family.value,
                "reason": "stored_rows_absent",
            },
        )
        for source_family in calculation_rows.absent_source_families
    ]


def _withholding_window_readback(
    ctx: typer.Context,
    command: PerModeloAggregationCommand,
) -> WithholdingWindowReadbackPayload | None:
    """Read the current exact mutation baseline without exposing evidence rows.

    Invoice-backed withholding capture and an omitted aggregate invocation
    both arrive here after the shared producer has either committed or made no
    change.  The read is intentionally separate from the aggregation result:
    it preserves the service's optimistic-concurrency and immutable-generation
    contracts instead of reconstructing a token from aggregation data.
    """
    if command.modelo not in _PERIODIC_WINDOW_MODELOS:
        return None
    scope = WithholdingWindowScope(modelo=command.modelo, period=command.period)
    service = withholding_observation_service(ctx, bucket_id=active_bucket_id_or_refuse())
    state = service.read_window(scope)
    generation_audit = None if state.generation == 0 else service.read_generation(scope, state.baseline.generation_id)
    return WithholdingWindowReadbackPayload.from_window_state(state, generation_audit=generation_audit)


def _aggregate_output_lines(
    result: PerModeloAggregationResult, *, clave_breakdown: tuple[WithholdingClaveBreakdown, ...], notices: list[Notice]
) -> list[str]:
    """Render the text envelope lines for one per-modelo aggregation."""
    source_kinds = ", ".join(source_kind.value for source_kind in result.source_kinds) or "-"
    lines = [
        "operation\tmodelo.aggregate",
        f"modelo\t{result.modelo}",
        f"period\t{result.period.registry_token}",
        f"provider\t{result.provider.value}",
        f"observation_count\t{result.log_fields.observation_count}",
        f"source_kinds\t{source_kinds}",
        f"result_row_count\t{result.log_fields.result_row_count}",
    ]
    if clave_breakdown:
        lines.append("clave\tpercepcion_count\tpercibido_total\tretencion_total")
        lines.extend(
            f"clave_breakdown\t{row.clave.value}\t{row.percepcion_count}\t{row.percibido_total}\t{row.retencion_total}"
            for row in clave_breakdown
        )
    lines.extend(notice.message for notice in notices)
    return lines


def _parse_typed_cli_observations[ObservationT: BaseModel](
    values: list[str] | None, *, model: type[ObservationT], flag: str
) -> tuple[ObservationT, ...]:
    """Parse raw JSON observation objects into typed application records."""
    parsed: list[ObservationT] = []
    for raw in values or ():
        try:
            top = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(tr("cli.app.modelo.aggregate.json_parse_error", flag=flag, pos=exc.pos)) from exc
        if not isinstance(top, dict):
            raise typer.BadParameter(tr("cli.app.modelo.aggregate.json_not_object", flag=flag))
        try:
            parsed.append(model.model_validate_json(raw))
        except ValidationError as exc:
            details = "; ".join(f"{'.'.join(str(s) for s in e['loc'])}: {e['msg']}" for e in exc.errors())
            raise typer.BadParameter(
                tr("cli.app.modelo.aggregate.json_validation_error", flag=flag, details=details)
            ) from exc
    return tuple(parsed)


__all__ = ["aggregate_modelo"]


def aggregate_modelo(
    ctx: typer.Context,
    modelo: str,
    year: int,
    period: str,
    counterpart_observation: list[str] | None = None,
    foreign_asset_observation: list[str] | None = None,
    received_invoice_retencion: list[str] | None = None,
    ledger_payment_withholding: list[str] | None = None,
) -> None:
    """Delegate per-modelo aggregation execution to the backend service."""
    operation = authority_operation(ctx)
    with validating_governed_facts(operation):
        _refuse_misplaced_ledger_payment_withholding(
            modelo,
            ledger_payment_withholding=ledger_payment_withholding,
            received_invoice_retencion=received_invoice_retencion,
        )
        if modelo == Modelo("123").value and received_invoice_retencion:
            raise typer.BadParameter(tr("cli.app.modelo.aggregate.m123_ledger_payment_only"))
        command = PerModeloAggregationCommand(
            modelo=modelo,
            period=resolve_year_period(year, period, modelo=modelo),
            counterpart_observations=_parse_typed_cli_observations(
                counterpart_observation, model=CounterpartObservation, flag="--counterpart-observation"
            ),
            foreign_asset_observations=_parse_typed_cli_observations(
                foreign_asset_observation, model=ForeignAssetIngestObservation, flag="--foreign-asset-observation"
            ),
        )
        ledger_payment_requests = _parse_typed_cli_observations(
            ledger_payment_withholding,
            model=LedgerPaymentWithholdingEvidenceRequest,
            flag="--ledger-payment-withholding",
        )
        if ledger_payment_requests:
            command = _capture_ledger_payment_withholding_into_command(ctx, command, ledger_payment_requests[0])
        else:
            invoice_withholding_requests = _parse_typed_cli_observations(
                received_invoice_retencion,
                model=InvoiceWithholdingEvidenceRequest,
                flag="--received-invoice-retencion",
            )
            command = _capture_invoice_withholding_into_command(ctx, command, invoice_withholding_requests)
        calculation_rows = _read_calculation_withholding_rows(ctx, command)
        if calculation_rows is not None:
            command = command.model_copy(update={"retencion_observations": calculation_rows.retenciones or ()})
    result = aggregate_per_modelo(command, operation=operation)
    clave_breakdown = _clave_breakdown(calculation_rows)
    aggregate_result = ModeloAggregateResult.from_aggregation_result(
        result,
        clave_breakdown=clave_breakdown,
        withholding_window=_withholding_window_readback(ctx, command),
    )
    notices = _calculation_rows_absent_notices(command, calculation_rows)
    lines = _aggregate_output_lines(result, clave_breakdown=clave_breakdown, notices=notices)
    emit_envelope(ctx, command="modelo.aggregate", result=aggregate_result, lines=lines, notices=notices)
