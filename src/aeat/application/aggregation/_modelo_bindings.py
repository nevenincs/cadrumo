"""Repository-backed source-mesh resolvers for modelo registry bindings.

This module is the calculation-facing bridge from bucket-local stores to
:class:`~._source_mesh.CalculationSourceResolution`. Each resolver owns one
:class:`~aeat.core.aggregation.BindingSourceKind`, reads the active
:class:`~._source_mesh.CalculationSourceContext`, and materialises binding
values declared on the snapshot's
:class:`~aeat.domain.calculations.registry.ModeloRevision`.

The IVA, Renta income, Renta expense, and M130 gasto resolvers delegate their
ledger projection to :mod:`~._iva_ledger`, :mod:`~._renta_income_ledger`,
:mod:`~._renta_ledger`, and :mod:`~._renta_gasto_ledger`. The retenciones
resolver reads the dedicated per-perceptor store through
:mod:`~._retencion_observations_repository`. The separate
:mod:`~._oss_ioss` and :mod:`~._withholding_source` modules follow the same
source-mesh contract for Modelo 369 and Modelo 190 detail counts.

Invoice-backed checks use
:class:`~aeat.domain.invoices.InvoiceCatalogueRepository` only as supporting
evidence: Modelo 303 domestic IVA remains ledger-owned, while Renta expense
aggregation can attach purchase-invoice evidence to transaction rows before
producing the shared :class:`~._source_mesh.CalculationSourceResolution`.

Declarable observations that no registry binding consumes are reported as
source diagnostics rather than silently blanking the filed calculation.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...adapters.persistence.storage.errors import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    StorageValidationError,
)
from ...core import BindingSourceKind, Modelo, Period, PeriodError
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    IvaLedgerObservation,
    ModeloRevision,
    resolve_ledger_iva_aggregation_binding_values,
    resolve_ledger_renta_expense_aggregation_binding_values,
    resolve_ledger_renta_gasto_aggregation_binding_values,
    resolve_ledger_renta_income_aggregation_binding_values,
    resolve_retenciones_aggregation_binding_values,
    unsupported_ledger_iva_observations,
    unsupported_ledger_renta_expense_observations,
    unsupported_ledger_renta_gasto_observations,
    unsupported_ledger_renta_income_observations,
    validated_casilla_id,
)
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogueRepository,
    InvoiceCatalogueRepositoryProtocol,
    InvoicePersistenceError,
    invoice_line_to_iva_observation,
)
from ...domain.renta import RentaDeductibleExpenseObservation
from ...domain.transactions import TransactionCatalogueRepositoryProtocol, TransactionPersistenceError
from ._errors import AggregationValidationError, t
from ._iva_ledger import IvaLedgerAggregationIssueReason, aggregate_iva_ledger_observations_from_repositories
from ._renta_gasto_ledger import aggregate_renta_gasto_ledger_from_repositories
from ._renta_income_ledger import (
    aggregate_renta_income_ledger_from_repositories,
    aggregate_renta_m100_income_ledger_from_repositories,
)
from ._renta_ledger import aggregate_renta_ledger_expenses_from_repositories
from ._retencion_observations_repository import RetencionObservationRepository
from ._retenciones import (
    aggregate_retenciones_115,
    aggregate_retenciones_180,
    aggregate_retenciones_193,
)
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)

_STORAGE_DEGRADATION_ERRORS = (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    InvoicePersistenceError,
    StorageValidationError,
    TransactionPersistenceError,
)
_IVA_SOURCE_DIAGNOSTIC_SUPPRESSED_REASONS = frozenset(
    {
        IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
        IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION,
    },
)
_M130_RETENCIONES_BINDING_ID: BindingId = "modelo-130-actividad-economica-retenciones-cumulative"
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M303_STANDARD_DOMESTIC_IVA_CUOTA_BINDINGS: tuple[BindingId, ...] = (
    "modelo-303-iva-repercutido-general-cuota",
    "modelo-303-iva-repercutido-reducido-cuota",
    "modelo-303-iva-repercutido-super-reducido-cuota",
    "modelo-303-iva-soportado-interiores-cuota",
)
_M303_INVOICE_EVIDENCE_SAMPLE_LIMIT = 5


class LedgerIvaAggregationSourceResolver:
    """Resolve ``ledger_iva_aggregation`` bindings from the transaction ledger.

    Owns :attr:`BindingSourceKind.LEDGER_IVA_AGGREGATION`, projects IVA
    observations through :func:`~._iva_ledger.aggregate_iva_ledger_observations_from_repositories`,
    and returns a :class:`~._source_mesh.CalculationSourceResolution` with
    source issues, unrouted-observation diagnostics, and transaction provenance.
    """

    resolver_id = "ledger_iva_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_IVA_AGGREGATION,)

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._invoice_repository = invoice_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_iva_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        try:
            aggregation = aggregate_iva_ledger_observations_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period,
                transaction_repository=self._transaction_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        transaction_ids = {observation.ledger_id for observation in aggregation.observations}
        transaction_ids.update(reference.transaction_id for reference in aggregation.prorrata_references)
        binding_values = resolve_ledger_iva_aggregation_binding_values(
            context.revision,
            aggregation.observations,
        )
        _raise_if_m303_invoice_domestic_iva_would_be_silent(
            context=context,
            period=aggregation_period,
            transaction_binding_values=binding_values,
            invoice_repository=self._invoice_repository,
        )
        # Reuse the fail-closed candidate-path screen as a NON-blocking advisory on
        # the calculate path: a declarable IVA observation whose category/rate/flow
        # triple no ``ledger_iva_aggregation`` binding selects would otherwise be
        # silently dropped. Surface it (calculate still succeeds) so the operator
        # sees the unrouted IVA rather than filing an under-declared form
        # (no-silent-under-declaration). The category/rate/flow axes are the
        # observation's own provenance — no legal_ref is fabricated.
        unconsumed = unsupported_ledger_iva_observations(context.revision, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            source_transaction_ids=tuple(sorted(transaction_ids)),
            diagnostics=tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_iva_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
                if issue.reason not in _IVA_SOURCE_DIAGNOSTIC_SUPPRESSED_REASONS
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_iva_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable IVA observation {observation.ledger_id!r} "
                        f"(category={observation.category.value!r}, rate_kind={observation.rate_kind.value!r}, "
                        f"flow_direction={observation.flow_direction.value!r}) is not consumed by any "
                        f"ledger_iva_aggregation binding on revision {context.revision.id!r}; "
                        "its base/cuota is not declared on this calculation"
                    ),
                )
                for observation in unconsumed
            ),
            provenance=(
                tuple(
                    CalculationSourceProvenance(
                        source_kind="ledger_iva_aggregation",
                        source_ref=f"transaction:{observation.ledger_id}",
                    )
                    for observation in aggregation.observations
                )
                + tuple(
                    CalculationSourceProvenance(
                        source_kind="ledger_iva_aggregation",
                        source_ref=f"prorrata:{reference.transaction_id}",
                    )
                    for reference in aggregation.prorrata_references
                )
            ),
        )


class LedgerRentaExpenseAggregationSourceResolver:
    """Resolve ``ledger_renta_expense_aggregation`` bindings for Renta expenses.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_EXPENSE_AGGREGATION` and folds
    transaction rows plus purchase-invoice evidence through
    :func:`~._renta_ledger.aggregate_renta_ledger_expenses_from_repositories`.
    It reports source issues and unrouted deductible expenses on the returned
    :class:`~._source_mesh.CalculationSourceResolution`.
    """

    resolver_id = "ledger_renta_expense_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_RENTA_EXPENSE_AGGREGATION,)

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._invoice_repository = invoice_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_expense_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        try:
            aggregation = aggregate_renta_ledger_expenses_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period_for_modelo(
                    filing_year=context.filing_year,
                    code=context.period.registry_token,
                ),
                transaction_repository=self._transaction_repository,
                invoice_repository=self._invoice_repository,
                profile_year=context.filing_year,
                modelo=context.modelo,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        # Fail-closed advisory parity with the IVA screen: a non-zero declarable
        # expense whose (modelo, period, target_casilla_id) matches no
        # ledger_renta_expense_aggregation binding would otherwise be silently
        # dropped (no-silent-under-declaration). Calculate still succeeds; the
        # operator sees the unrouted expense instead of an under-declared form.
        unrouted = unsupported_ledger_renta_expense_observations(context.revision, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_renta_expense_aggregation_binding_values(
                context.revision,
                aggregation.observations,
            ),
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_renta_expense_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_renta_expense_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable renta expense observation "
                        f"(modelo={str(observation.modelo)!r}, period={observation.period!r}, "
                        f"target_casilla_id={observation.target_casilla_id!r}, "
                        f"deductible_amount={observation.deductible_amount}) is not consumed by any "
                        f"ledger_renta_expense_aggregation binding on revision {context.revision.id!r}; "
                        "its deductible amount is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=tuple(
                provenance
                for observation in aggregation.observations
                for provenance in _renta_observation_provenance(observation)
            ),
        )


class LedgerRentaIncomeAggregationSourceResolver:
    """Resolve ``ledger_renta_income_aggregation`` actividad-income bindings.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION`. Modelo 130
    uses the cumulative-quarter income path, while Modelo 100 uses the annual
    activity-income path over the same ledger eligibility rules.
    """

    resolver_id = "ledger_renta_income_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol | None = None) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_income_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        # Modelo 100 (annual IRPF) aggregates actividad income over the full
        # ejercicio into casilla 0171; Modelo 130 uses the cumulative-quarter path.
        # Same source kind, same actividad eligibility, different window/target.
        income_aggregator = (
            aggregate_renta_m100_income_ledger_from_repositories
            if str(context.modelo) == Modelo.M100.value
            else aggregate_renta_income_ledger_from_repositories
        )
        try:
            aggregation = income_aggregator(
                bucket_id=context.bucket_id,
                period=aggregation_period,
                transaction_repository=self._transaction_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        binding_values = resolve_ledger_renta_income_aggregation_binding_values(
            context.revision,
            aggregation.observations,
        )
        # Fail-closed advisory parity with the IVA screen: a non-zero declarable
        # income whose target_casilla_id matches no ledger_renta_income_aggregation
        # binding would otherwise be silently dropped (no-silent-under-declaration).
        unrouted = unsupported_ledger_renta_income_observations(context.revision, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            bound_inputs_by_casilla_id=_m130_retenciones_backend_inputs(context, binding_values),
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_renta_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_renta_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable renta income observation (target_casilla_id="
                        f"{observation.target_casilla_id!r}, gross_amount={observation.gross_amount}) "
                        f"is not consumed by any ledger_renta_income_aggregation binding on revision "
                        f"{context.revision.id!r}; its income is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_renta_income_aggregation",
                    source_ref=f"transaction:{observation.transaction_id}",
                )
                for observation in aggregation.observations
            ),
        )


def _m130_retenciones_backend_inputs(
    context: CalculationSourceContext,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    if str(context.modelo) != Modelo.M130.value:
        return {}
    value = binding_values.get(_M130_RETENCIONES_BINDING_ID)
    if value is None:
        return {}
    return {_M130_RETENCIONES_CASILLA: value}


class LedgerRentaGastoAggregationSourceResolver:
    """Source mesh resolver for repository-backed M130 deductible-expense (gasto) bindings.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_GASTO_AGGREGATION`. This is the
    OUTGOING sibling of :class:`LedgerRentaIncomeAggregationSourceResolver`: it
    folds deductible business expenses into Modelo 130 casilla 02 over the same
    cumulative year-to-date quarterly window and emits an unrouted-observation
    diagnostic for declarable gastos no binding consumes.
    """

    resolver_id = "ledger_renta_gasto_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_RENTA_GASTO_AGGREGATION,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol | None = None) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_gasto_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        try:
            aggregation = aggregate_renta_gasto_ledger_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period,
                transaction_repository=self._transaction_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        # Fail-closed advisory parity with the income screen: a non-zero
        # declarable gasto whose target_casilla_id matches no
        # ledger_renta_gasto_aggregation binding would otherwise be silently
        # dropped (no-silent-under-declaration). Calculate still succeeds; the
        # operator sees the unrouted expense instead of an under-declared form.
        unrouted = unsupported_ledger_renta_gasto_observations(context.revision, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_renta_gasto_aggregation_binding_values(
                context.revision,
                aggregation.observations,
            ),
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_renta_gasto_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_renta_gasto_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable renta gasto observation (target_casilla_id="
                        f"{observation.target_casilla_id!r}, deductible_amount={observation.deductible_amount}) "
                        f"is not consumed by any ledger_renta_gasto_aggregation binding on revision "
                        f"{context.revision.id!r}; its deductible expense is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_renta_gasto_aggregation",
                    source_ref=f"transaction:{observation.transaction_id}",
                )
                for observation in aggregation.observations
            ),
        )


def _raise_if_m303_invoice_domestic_iva_would_be_silent(
    *,
    context: CalculationSourceContext,
    period: Period,
    transaction_binding_values: Mapping[BindingId, Decimal],
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
) -> None:
    """Refuse M303 when domestic invoice IVA would be absent from ledger totals.

    Modelo 303's domestic IVA boxes are sourced from ``ledger_iva_aggregation``:
    the transaction ledger is the filing authority. A bucket can also carry real
    invoice catalogue evidence, but there is no domestic-IVA invoice binding
    family for M303. If positive Spanish invoice IVA exists for the same period
    and its standard domestic cuota would exceed the transaction-ledger cuota
    that the filing is about to use, calculating a zero/subtotal filing would
    silently under-declare. Refuse and require the operator to link/classify the
    transactions that feed the canonical ledger path.
    """
    if str(context.modelo) != Modelo.M303.value:
        return
    invoice_observations, invoice_ids = _m303_standard_domestic_invoice_iva_observations(
        context=context,
        period=period,
        invoice_repository=invoice_repository,
    )
    if not invoice_observations:
        return
    invoice_binding_values = resolve_ledger_iva_aggregation_binding_values(context.revision, invoice_observations)
    missing_binding_values = {
        binding_id: invoice_value - transaction_value
        for binding_id in _M303_STANDARD_DOMESTIC_IVA_CUOTA_BINDINGS
        if (invoice_value := invoice_binding_values.get(binding_id, Decimal("0"))) > (
            transaction_value := transaction_binding_values.get(binding_id, Decimal("0"))
        )
    }
    if not missing_binding_values:
        return
    raise AggregationValidationError(
        t("errors.error.error_modelo_aggregation_binding"),
        context={
            "reason": "invoice_domestic_iva_not_in_transaction_ledger",
            "modelo": str(context.modelo),
            "filing_year": str(context.filing_year),
            "period": context.period.registry_token,
            "source_kind": "ledger_iva_aggregation",
            "invoice_domestic_iva_excess_by_binding": {
                str(binding_id): str(amount) for binding_id, amount in missing_binding_values.items()
            },
            "invoice_ids": tuple(sorted(invoice_ids)[:_M303_INVOICE_EVIDENCE_SAMPLE_LIMIT]),
            "invoice_count": str(len(invoice_ids)),
        },
        suggestion=(
            "Link and classify the domestic IVA invoices into the transaction ledger "
            "before calculating Modelo 303; invoice-only IVA evidence is not a Modelo 303 filing source."
        ),
    )


def _m303_standard_domestic_invoice_iva_observations(
    *,
    context: CalculationSourceContext,
    period: Period,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
) -> tuple[tuple[IvaLedgerObservation, ...], tuple[str, ...]]:
    try:
        repository = invoice_repository or InvoiceCatalogueRepository(bucket_id=context.bucket_id)
        catalogue = repository.load()
    except _STORAGE_DEGRADATION_ERRORS:
        return (), ()
    observations: list[IvaLedgerObservation] = []
    invoice_ids: set[str] = set()
    for invoice in catalogue.values():
        if not _m303_standard_domestic_invoice_in_period(invoice, context=context, period=period):
            continue
        for line_index, line in enumerate(invoice.lines):
            if line.iva_amount <= Decimal("0"):
                continue
            observations.append(
                invoice_line_to_iva_observation(
                    invoice_id=f"invoice:{invoice.invoice_id}:{line_index}",
                    issued_at=invoice.issued_at,
                    invoice_kind=invoice.kind,
                    iva_rate=line.iva_rate,
                    base_amount=line.subtotal,
                    iva_amount=line.iva_amount,
                ),
            )
            invoice_ids.add(invoice.invoice_id)
    return tuple(observations), tuple(invoice_ids)


def _m303_standard_domestic_invoice_in_period(
    invoice: Invoice,
    *,
    context: CalculationSourceContext,
    period: Period,
) -> bool:
    return (
        invoice.bucket_id == context.bucket_id
        and period.contains(invoice.issued_at)
        and invoice.counterparty_country.strip().upper() == "ES"
    )


def aggregation_period_for_modelo(*, filing_year: int, code: str) -> Period:
    """Translate a canonical ``StandardPeriodCode`` token to a core period.

    Accepts only the span-shaped canonical AEAT tokens the calc engine and the
    CLI ledger filter share: quarters (``1T``-``4T``), the annual period
    (``0A``), and months (``01``-``12``). The result is the typed core
    :class:`Period` consumed by ledger filters. Any other token raises
    :class:`AggregationValidationError`.
    """
    normalized = code.strip().upper()
    try:
        resolved = Period.from_year_and_code(filing_year, normalized)
    except PeriodError as exc:
        raise AggregationValidationError(
            t("aggregation.modelo_bindings.errors.unsupported_period"),
            context={"filing_year": str(filing_year), "period": code},
        ) from exc
    if not resolved.has_date_span():
        raise AggregationValidationError(
            t("aggregation.modelo_bindings.errors.unsupported_period"),
            context={"filing_year": str(filing_year), "period": code},
        )
    return resolved


def _revision_has_binding_source(revision: ModeloRevision, source: str) -> bool:
    return any(binding.source == source for binding in revision.bindings)


def _empty_source_resolution(
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    return CalculationSourceResolution(resolver_id=resolver_id, owned_sources=owned_sources)


#: Retenciones modelos whose registry declares ``retenciones_aggregation`` bindings,
#: mapped to their validated per-perceptor aggregator. Modelo 115 uses the quarterly
#: URBAN_RENTAL aggregate for casillas 01/02. Modelos 180/193 use the annual
#: aggregate for the distinct-NIF perceptor count; their monetary totals remain on
#: relation-prefill. Modelo 190 is not included: its annual count is
#: "percepciones", a distinct perceptor/clave/subclave figure handled by
#: :class:`~._withholding_source.WithholdingSourceResolver`.
_RETENCIONES_AGGREGATORS = {
    Modelo.M115.value: aggregate_retenciones_115,
    Modelo.M180.value: aggregate_retenciones_180,
    Modelo.M193.value: aggregate_retenciones_193,
}


class RetencionesAggregationSourceResolver:
    """Source mesh resolver for the dedicated per-perceptor retención store (RET-1).

    Reads the bucket-scoped per-perceptor retención observations
    (:class:`~._retencion_observations_repository.RetencionObservationRepository`)
    for the modelo's period and materialises the declared retenciones aggregation
    bindings through the matching validated aggregator. Modelo 115 consumes the
    quarterly URBAN_RENTAL count/base; annual summary modelos consume the same
    family store for their distinct-NIF count. Modelo 190's percepciones count is
    handled by :class:`~._withholding_source.WithholdingSourceResolver`.
    """

    resolver_id = "retenciones_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.RETENCIONES_AGGREGATION,)

    def __init__(self, *, retencion_repository: RetencionObservationRepository | None = None) -> None:
        self._retencion_repository = retencion_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "retenciones_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)
        aggregator = _RETENCIONES_AGGREGATORS.get(str(context.modelo))
        if aggregator is None:
            # Defensive: a revision declares the source for a modelo with no
            # retenciones aggregator. Resolve empty rather than guess values.
            return _empty_source_resolution(self.resolver_id, self.owned_sources)
        repository = self._retencion_repository or RetencionObservationRepository()
        try:
            observations = repository.load_observations(str(context.modelo), context.period)
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        if not observations:
            raise AggregationValidationError(
                t("aggregation.retenciones.errors.perceptor_observations_missing"),
                context={
                    "modelo": str(context.modelo),
                    "filing_year": str(context.filing_year),
                    "period": context.period.registry_token,
                    "source_kind": "retenciones_aggregation",
                },
                suggestion=(
                    "Supply the per-perceptor retención observations "
                    "(`aeat app modelo aggregate --retencion-observation`) before calculating."
                ),
            )
        aggregation = aggregator(tuple(observations), period=context.period)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_retenciones_aggregation_binding_values(context.revision, aggregation),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="retenciones_aggregation",
                    source_ref=f"perceptor:{rollup.perceptor_nif}",
                )
                for rollup in aggregation.rollups
            ),
        )


def _renta_observation_provenance(
    observation: RentaDeductibleExpenseObservation,
) -> tuple[CalculationSourceProvenance, ...]:
    provenance = [
        CalculationSourceProvenance(
            source_kind="ledger_renta_expense_aggregation",
            source_ref=f"transaction:{observation.transaction_id}",
        ),
    ]
    if observation.invoice_id is not None:
        provenance.append(
            CalculationSourceProvenance(
                source_kind="ledger_renta_expense_aggregation",
                source_ref=f"purchase-invoice-evidence:{observation.invoice_id}",
            ),
        )
    return tuple(provenance)


__all__ = [
    "LedgerIvaAggregationSourceResolver",
    "LedgerRentaExpenseAggregationSourceResolver",
    "LedgerRentaGastoAggregationSourceResolver",
    "LedgerRentaIncomeAggregationSourceResolver",
    "aggregation_period_for_modelo",
]
