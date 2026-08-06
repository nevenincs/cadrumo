"""Repository-backed source-mesh resolvers for modelo registry bindings.

This module is the calculation-facing bridge from bucket-local stores to
:class:`~._source_mesh.CalculationSourceResolution`. Each resolver owns one
:class:`~core.BindingSourceKind`, reads the active
:class:`~._source_mesh.CalculationSourceContext`, and materialises binding
values declared on the snapshot's
:class:`~domain.calculations.registry.ModeloRevision`.

The IVA, Renta income, Renta expense, and M130 gasto resolvers delegate their
ledger projection to :mod:`~._iva_ledger`, :mod:`~._renta_income_ledger`,
:mod:`~._renta_ledger`, and :mod:`~._renta_gasto_ledger`. The retenciones
resolver reads the dedicated per-perceptor store through
:mod:`~._retencion_observations_repository`. The separate
:mod:`~._oss_ioss` and :mod:`~._withholding_source` modules follow the same
source-mesh contract for Modelo 369 and Modelo 190 detail counts.

Invoice-backed checks use
:class:`~domain.invoices.InvoiceCatalogueRepository` only as supporting
evidence: Modelo 303 domestic IVA remains ledger-owned, while Renta expense
aggregation can attach purchase-invoice evidence to transaction rows before
producing the shared :class:`~._source_mesh.CalculationSourceResolution`.

Declarable observations that no registry binding consumes are reported as
source diagnostics rather than silently blanking the filed calculation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.usage_ratios import load_usage_ratios
from ...adapters.persistence.storage import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    StorageValidationError,
)
from ...core import BindingSourceKind, M210GrossIncomeSourceMode, Modelo, Period, PeriodError, StandardPeriodCode
from ...domain.calculations.registry import (
    BindingId,
    CasillaDefinition,
    CasillaId,
    IvaLedgerObservation,
    ModeloRevision,
    UngroundedRentaIncome,
    resolve_ledger_impatriado_income_aggregation_binding_values,
    resolve_ledger_irnr_income_aggregation_binding_values,
    resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values,
    resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values,
    resolve_ledger_renta_income_aggregation_binding_values,
    resolve_retenciones_aggregation_binding_values,
    ungrounded_ledger_renta_income_observations,
    unsupported_ledger_impatriado_income_observations,
    unsupported_ledger_irnr_income_observations,
    unsupported_ledger_iva_observations,
    unsupported_ledger_renta_gastos_estimacion_directa_observations,
    unsupported_ledger_renta_gastos_pago_fraccionado_observations,
    unsupported_ledger_renta_income_observations,
    validated_casilla_id,
)
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogueRepositoryProtocol,
    InvoicePersistenceError,
    invoice_line_to_iva_observation,
)
from ...domain.modelos import Modelo210AgrupacionRentaRow
from ...domain.renta import RentaDeductibleExpenseObservation
from ...domain.transactions import (
    OutOfWindowTransactionSummary,
    TransactionCatalogueRepositoryProtocol,
    TransactionPersistenceError,
)
from ...domain.usage_ratios import UsageRatioPersistenceError
from ._errors import AggregationValidationError, t
from ._impatriado_income_ledger import aggregate_impatriado_income_ledger_from_repositories
from ._invoice_devengo import (
    devengo_proxy_attribution_diagnostics,
    invoice_devengo_in_period,
    resolve_invoice_devengo,
)
from ._irnr_income_ledger import IrnrIncomeObservation, aggregate_irnr_income_ledger_from_repositories
from ._iva_ledger import (
    IvaLedgerAggregationIssueReason,
    IvaLedgerProrrataApportionment,
    aggregate_iva_ledger_observations_from_repositories,
    resolve_iva_ledger_binding_values,
)
from ._renta_gasto_ledger import aggregate_renta_gasto_ledger_from_repositories
from ._renta_income_ledger import (
    RentaIncomeObservation,
    SalesInvoiceEvidenceRefusal,
    aggregate_renta_income_ledger_from_repositories,
    aggregate_renta_m100_income_ledger_from_repositories,
)
from ._renta_ledger import aggregate_renta_ledger_expenses_from_repositories
from ._retencion_observations_repository import RetencionObservationRepository
from ._retencion_rate_advisory import (
    administrador_retencion_rate_advisory_observations,
    inferred_actividad_retencion_rate_advisory_observations,
)
from ._retenciones import (
    RetencionesAggregation,
    RetencionObservation,
    aggregate_retenciones_111,
    aggregate_retenciones_115,
    aggregate_retenciones_123,
    aggregate_retenciones_180,
    aggregate_retenciones_190,
    aggregate_retenciones_193,
)
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    out_of_window_summary_source_diagnostic,
    storage_degradation_resolution,
)

_STORAGE_DEGRADATION_ERRORS = (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    InvoicePersistenceError,
    StorageValidationError,
    TransactionPersistenceError,
    UsageRatioPersistenceError,
)
_IVA_SOURCE_DIAGNOSTIC_SUPPRESSED_REASONS = frozenset(
    {
        IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
        IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION,
    },
)
_M130_RETENCIONES_BINDING_ID: BindingId = "modelo-130-actividad-economica-retenciones-cumulative"
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M210_RENDIMIENTOS_INTEGROS_CASILLA: CasillaId = validated_casilla_id(
    "rendimientos_integros",
    surface="_M210_RENDIMIENTOS_INTEGROS_CASILLA",
)

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
        binding_values = resolve_iva_ledger_binding_values(
            context.revision,
            aggregation.observations,
            prorrata_apportionment=aggregation.prorrata_apportionment,
        )
        devengo_compared_invoices = _raise_if_m303_invoice_domestic_iva_would_be_silent(
            context=context,
            period=aggregation_period,
            transaction_binding_values=binding_values,
            invoice_repository=self._invoice_repository,
            prorrata_apportionment=aggregation.prorrata_apportionment,
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
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
            )
            + devengo_proxy_attribution_diagnostics(
                devengo_compared_invoices,
                source_kind="ledger_iva_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
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
                + _iva_prorrata_apportionment_provenance(
                    context.revision,
                    aggregation_period,
                    aggregation.prorrata_apportionment,
                )
            ),
        )


class LedgerRentaGastosEstimacionDirectaAggregationSourceResolver:
    """Resolve ``ledger_renta_gastos_estimacion_directa_aggregation`` bindings for Renta expenses.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION` and folds
    transaction rows plus purchase-invoice evidence through
    :func:`~._renta_ledger.aggregate_renta_ledger_expenses_from_repositories`.
    It reports source issues and unrouted deductible expenses on the returned
    :class:`~._source_mesh.CalculationSourceResolution`.
    """

    resolver_id = "ledger_renta_gastos_estimacion_directa_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
    )

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._invoice_repository = invoice_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_gastos_estimacion_directa_aggregation"):
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
                usage_ratios=load_usage_ratios(bucket_id=context.bucket_id).ratios,
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
        # ledger_renta_gastos_estimacion_directa_aggregation binding would otherwise be silently
        # dropped (no-silent-under-declaration). Calculate still succeeds; the
        # operator sees the unrouted expense instead of an under-declared form.
        unrouted = unsupported_ledger_renta_gastos_estimacion_directa_observations(
            context.revision, aggregation.observations
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values(
                context.revision,
                aggregation.observations,
            ),
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable renta gastos observation "
                        f"(modelo={str(observation.modelo)!r}, period={observation.period!r}, "
                        f"target_casilla_id={observation.target_casilla_id!r}, "
                        f"deductible_amount={observation.deductible_amount}) is not consumed by any "
                        f"ledger_renta_gastos_estimacion_directa_aggregation binding "
                        f"on revision {context.revision.id!r}; "
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

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._invoice_repository = invoice_repository

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
                invoice_repository=self._invoice_repository,
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
        # Second, distinct screen: rows a binding DOES consume but whose
        # contribution rests on bank cash because no invoice substrate was
        # recorded. The fallback is deliberately kept (dropping an untagged
        # income row under-declares by its whole value), so this is the only
        # thing standing between the operator and a silently mis-measured
        # income casilla.
        ungrounded = ungrounded_ledger_renta_income_observations(context.revision, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            bound_inputs_by_casilla_id=_m130_retenciones_backend_inputs(context, binding_values),
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_renta_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
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
            )
            + _ungrounded_income_diagnostics(ungrounded, resolver_id=self.resolver_id)
            + _unusable_sales_invoice_diagnostics(aggregation.observations, resolver_id=self.resolver_id)
            + inferred_actividad_retencion_rate_advisory_observations(
                aggregation.observations,
                bucket_id=context.bucket_id,
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_renta_income_aggregation",
                    source_ref=f"transaction:{observation.transaction_id}",
                )
                for observation in aggregation.observations
            ),
        )


# The character budget an advisory message must fit, read from the field that
# enforces it rather than restated as a literal -- a hardcoded copy silently
# stops matching the moment the model's own limit moves, and the failure lands
# as a ValidationError raised from inside the diagnostic that was supposed to
# keep the operator informed.
#
# An operator needs a handle on the offending rows, not the whole list, so the
# id sample is fitted to whatever budget the prose leaves. The count and the
# summed cash are always exact and the omission is always stated, so the list
# shortens but never becomes a silent cap.
_DIAGNOSTIC_MESSAGE_MAX: int = next(
    meta.max_length
    for meta in CalculationSourceDiagnostic.model_fields["message"].metadata
    if getattr(meta, "max_length", None) is not None
)


def _ungrounded_income_consequence(facts: frozenset[str]) -> str:
    """Describe what a missing base does to the income casilla, per declared fact.

    The two base-reading facts fail in opposite directions, so naming the
    consequence precisely is what makes the advisory actionable: an operator
    who reads "contributed nothing" knows the return is under-declared, while
    "bank cash stood in for the base" warns the figure may be wrong either way.

    Kept short deliberately: this text shares its 512-character diagnostic
    budget with the dropped-retención-credit clause added in
    :func:`_ungrounded_income_diagnostics`, so headroom here is headroom for
    the transaction-id sample, not free prose.
    """
    folds_cash = "ingresos_integros_sum" in facts
    contributes_zero = "taxable_base_sum" in facts
    if folds_cash and contributes_zero:
        return "bank cash filled the ingresos_integros_sum binding while taxable_base_sum got nothing"
    if contributes_zero:
        return "these rows contributed nothing to taxable_base_sum, under-declaring by their full base"
    return "bank cash stood in for the base imponible, which is not the ingresos íntegros this casilla declares"


def _ungrounded_income_diagnostics(
    ungrounded: UngroundedRentaIncome,
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Project base-less income contributions into ONE advisory per aggregation.

    Deliberately aggregate rather than per-row: an advisory that fires once per
    transaction trains operators to ignore it, and the actionable unit here is
    "how much of my declared income has no invoice behind it", not each row.
    The count and the summed cash are always exact; only the transaction-id
    list is abbreviated, and the omitted count is stated so the truncation is
    visible rather than silent.

    The id list is fitted to the diagnostic's own character budget rather than
    to a fixed number of ids. Bounding by id COUNT was a proxy for the real
    constraint: :class:`CalculationSourceDiagnostic` caps ``message`` at
    :data:`_DIAGNOSTIC_MESSAGE_MAX`, transaction ids are long and
    variable-length, and three of them already overflowed a five-id sample --
    raising ``ValidationError`` from inside the advisory and taking down the
    whole calculation. A safety net that crashes as soon as it has several
    things to report is worse than none, so the budget is now measured, not
    assumed.

    The message names both halves of the harm, not just the income
    mis-measurement. Every row this screen catches has grounding
    ``CASH_FALLBACK`` (no declared ``taxable_base``), and the withheld-amount
    inference in ``_renta_income_ledger`` refuses to run without that same
    base -- so each of these rows *also* contributes zero to the
    ``withheld_amount_sum`` binding, silently dropping the ISSUED-side
    retención credit (RIRPF art. 110.3.a) alongside the income figure. This is
    the credit the taxpayer is owed on income already invoiced to a client; it
    is unrelated to the per-perceptor retenedor-liability store a RECEIVED
    invoice routes into, which this screen never reads. The count and summed
    cash reused below are the same values the income clause already computed,
    not a second derivation.

    Returns an empty tuple when every consumed row declared its substrate.
    """
    observations = ungrounded.observations
    if not observations:
        return ()
    total = sum((observation.gross_amount for observation in observations), Decimal("0"))
    sampled = sorted(observation.transaction_id for observation in observations)
    preamble = (
        f"{len(observations)} actividad-económica income row(s) totalling {total} EUR lack a "
        f"taxable_base, so {_ungrounded_income_consequence(ungrounded.facts)}. Their retención "
        f"credit is also lost, since it needs the same missing base. Record with 'aeat app "
        f"ledger classify <transaction-id> --taxable-base <amount>'. Transactions: "
    )
    return (
        CalculationSourceDiagnostic(
            reason="ungrounded_income_substrate",
            source_kind="ledger_renta_income_aggregation",
            resolver_id=resolver_id,
            message=preamble + _fitted_id_list(sampled, budget=_DIAGNOSTIC_MESSAGE_MAX - len(preamble)),
        ),
    )


def _unusable_sales_invoice_diagnostics(
    observations: Sequence[RentaIncomeObservation],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Surface rows whose linked sales invoice could not be trusted.

    These rows are NOT excluded -- they contribute their bank cash, because the
    taxpayer was paid and that income is declarable whatever state its paperwork
    is in. What they lost is the invoice's base, cuota and retención, so the
    figure they contribute is the credited cash rather than the ingresos
    íntegros the casilla asks for. Without this advisory that downgrade is
    invisible: the row looks exactly like one that never had an invoice at all.

    One advisory per refusal reason, not per row: the actionable unit is "these
    links are unusable, and this is what is wrong with them", and a per-row
    advisory trains operators to ignore the channel. The id sample is fitted to
    the message budget by the same helper the ungrounded advisory uses, so a
    long list degrades to a count instead of raising out of the diagnostic and
    taking the calculation down with it.
    """
    by_reason: dict[SalesInvoiceEvidenceRefusal, list[RentaIncomeObservation]] = defaultdict(list)
    for observation in observations:
        if observation.sales_invoice_refusal is not None:
            by_reason[observation.sales_invoice_refusal].append(observation)
    diagnostics: list[CalculationSourceDiagnostic] = []
    for reason in sorted(by_reason, key=lambda member: member.value):
        rows = by_reason[reason]
        total = sum((row.gross_amount for row in rows), Decimal("0"))
        preamble = (
            f"{len(rows)} income row(s) totalling {total} EUR link a sales invoice that could not be "
            f"trusted ({reason.value}), so they declare bank cash instead of the invoice base and their "
            f"retención credit is lost. Repair the link or record the base directly. Transactions: "
        )
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="unusable_sales_invoice_evidence",
                source_kind="ledger_renta_income_aggregation",
                resolver_id=resolver_id,
                message=preamble
                + _fitted_id_list(
                    sorted(row.transaction_id for row in rows),
                    budget=_DIAGNOSTIC_MESSAGE_MAX - len(preamble),
                ),
            ),
        )
    return tuple(diagnostics)


def _fitted_id_list(identifiers: Sequence[str], *, budget: int) -> str:
    """Render ``identifiers`` into at most ``budget`` characters, stating omissions.

    Shows as many ids as fit alongside the "(and N more)" suffix that describes
    the ones it dropped -- the suffix is part of the budget, because a truncation
    notice that itself overflows would defeat the cap it exists to respect.

    Degrades rather than raises: when even one id plus its suffix cannot fit, it
    reports the bare count. The caller is an advisory about a measurement risk,
    so losing the id sample is acceptable where losing the whole diagnostic --
    and with it the calculation -- is not.
    """
    total = len(identifiers)
    for shown in range(total, 0, -1):
        remainder = total - shown
        candidate = ", ".join(identifiers[:shown]) + (f" (and {remainder} more)" if remainder else "")
        if len(candidate) <= budget:
            return candidate
    fallback = f"{total} transaction(s), ids omitted to fit the diagnostic length limit"
    return fallback if len(fallback) <= budget else ""


def _m130_retenciones_backend_inputs(
    context: CalculationSourceContext,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Redirect the retenciones binding's resolved value to casilla 06.

    This is the OUTPUT half of a fact that is declared with
    `target_casilla_id = "01"` in the registry (see the comment on the
    `modelo-130-actividad-economica-retenciones-cumulative` binding in
    `_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/
    0003-m130-income-cumulative.toml`). That selector field is the
    OBSERVATION-MATCH key -- it must stay "01" for the aggregation to see any
    rows at all -- not a declaration of where the aggregate lands. Casilla 06
    is hardcoded here because this binding family has no schema field to
    express "match on X's observations, output to Y's casilla" honestly; do
    not "fix" the selector to "06" without reading that TOML comment first,
    since doing so silently zeroes this value instead of redirecting it.
    """
    if str(context.modelo) != Modelo.M130.value:
        return {}
    value = binding_values.get(_M130_RETENCIONES_BINDING_ID)
    if value is None:
        return {}
    return {_M130_RETENCIONES_CASILLA: value}


class LedgerImpatriadoIncomeAggregationSourceResolver:
    """Resolve ``ledger_impatriado_income_aggregation`` Modelo 151 base bindings.

    Owns :attr:`BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION`. Modelo
    151 (régimen especial de impatriados, Ley Beckham) folds only Spanish-source
    (``source_jurisdiction == "ES"``) income into
    ``impatriado.base-liquidable-general`` over the full ejercicio; every
    foreign-source or jurisdiction-unresolved row is segregated by the classifier
    into a typed ``BECKHAM_FOREIGN_SOURCE_SEGREGATED`` issue and surfaced as a
    non-blocking source diagnostic rather than silently admitted or silently
    dropped (art. 93.2 LIRPF / art. 25.1.f TRLIRNR).
    """

    resolver_id = "ledger_impatriado_income_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol | None = None) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_impatriado_income_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        try:
            aggregation = aggregate_impatriado_income_ledger_from_repositories(
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
        binding_values = resolve_ledger_impatriado_income_aggregation_binding_values(
            context.revision,
            aggregation.observations,
        )
        # Fail-closed advisory: a non-zero ES-source income whose target casilla
        # matches no ledger_impatriado_income_aggregation binding would otherwise
        # be silently dropped from the base (no-silent-under-declaration).
        unrouted = unsupported_ledger_impatriado_income_observations(context.revision, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_impatriado_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_impatriado_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_impatriado_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable impatriado ES-source income observation (target_casilla_id="
                        f"{observation.target_casilla_id!r}, gross_amount={observation.gross_amount}) "
                        f"is not consumed by any ledger_impatriado_income_aggregation binding on revision "
                        f"{context.revision.id!r}; its income is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_impatriado_income_aggregation",
                    source_ref=f"transaction:{observation.transaction_id}",
                )
                for observation in aggregation.observations
            ),
        )


class LedgerIrnrIncomeAggregationSourceResolver:
    """Resolve the selected-code M210 ``ledger_irnr_income_aggregation`` source.

    This resolver owns M210 ``rendimientos_integros`` only when the persisted
    gross-income source mode is ``ledger``.
    It passes the durable official tipo-renta selection through to the classifier
    rather than using the conceptual rate token, so codes such as ``01`` and
    ``03`` cannot be merged merely because they share a rate concept.
    """

    resolver_id = "ledger_irnr_income_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if context.m210_gross_income_source_mode is not M210GrossIncomeSourceMode.LEDGER:
            # The registry declares the optional M210 source unconditionally so
            # its selector remains validated.  Manual mode deliberately elects
            # not to produce a value, though, and that is a handled source
            # state—not an unenrolled-source advisory on every manual M210 run.
            return _empty_source_resolution(self.resolver_id, self.owned_sources)
        if not _revision_has_binding_source(context.revision, "ledger_irnr_income_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)
        selected_official_tipo_renta_code = context.m210_official_tipo_renta_code
        if selected_official_tipo_renta_code is None:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                diagnostics=(
                    CalculationSourceDiagnostic(
                        reason="source_issue",
                        source_kind="ledger_irnr_income_aggregation",
                        resolver_id=self.resolver_id,
                        message=(
                            "M210 ledger income binding requires the durable official tipo-renta code selection; "
                            "the conceptual formula token cannot select a ledger source"
                        ),
                    ),
                ),
            )

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        try:
            aggregation = aggregate_irnr_income_ledger_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period,
                revision=context.revision,
                selected_official_tipo_renta_code=selected_official_tipo_renta_code,
                transaction_repository=self._transaction_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )

        binding_values = resolve_ledger_irnr_income_aggregation_binding_values(
            context.revision,
            aggregation.observations,
        )
        unrouted = unsupported_ledger_irnr_income_observations(context.revision, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            bound_inputs_by_casilla_id={
                _M210_RENDIMIENTOS_INTEGROS_CASILLA: aggregation.casilla_aggregation.casilla_values.get(
                    _M210_RENDIMIENTOS_INTEGROS_CASILLA,
                    Decimal("0"),
                ),
            },
            detail_rows=_irnr_annual_agrupacion_renta_rows(context, aggregation.observations),
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_irnr_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_irnr_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_irnr_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        "declarable M210 IRNR gross-income observation "
                        f"(target_casilla_id={observation.target_casilla_id!r}, "
                        f"gross_income_amount={observation.gross_income_amount}) is not consumed by any "
                        "ledger_irnr_income_aggregation binding on revision "
                        f"{context.revision.id!r}; its income is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_irnr_income_aggregation",
                    source_ref=f"transaction:{observation.transaction_id}",
                )
                for observation in aggregation.observations
            ),
        )


def _irnr_annual_agrupacion_renta_rows(
    context: CalculationSourceContext,
    observations: Sequence[IrnrIncomeObservation],
) -> tuple[Modelo210AgrupacionRentaRow, ...]:
    """Derive annual M210 grouping evidence from the admitted classifications."""
    if context.period.standard_code is not StandardPeriodCode.ANNUAL:
        return ()
    return tuple(
        Modelo210AgrupacionRentaRow(
            source_id=observation.transaction_id,
            tipo_renta_code=observation.official_tipo_renta_code,
            importe=observation.gross_income_amount,
            tipo_gravamen=observation.applicable_rate,
            pagador_mode=observation.payer_mode,
            pagador_id=observation.payer_id,
            deriva_de_bien_derecho=observation.asset_or_right_id is not None,
            bien_derecho_id=observation.asset_or_right_id,
        )
        for observation in observations
    )


class LedgerRentaGastosPagoFraccionadoAggregationSourceResolver:
    """Source mesh resolver for repository-backed M130 deductible-expense (gasto) bindings.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION`. This is the
    OUTGOING sibling of :class:`LedgerRentaIncomeAggregationSourceResolver`: it
    folds deductible business expenses into Modelo 130 casilla 02 over the same
    cumulative year-to-date quarterly window and emits an unrouted-observation
    diagnostic for declarable gastos no binding consumes.
    """

    resolver_id = "ledger_renta_gastos_pago_fraccionado_aggregation"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol | None = None) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_gastos_pago_fraccionado_aggregation"):
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
        # ledger_renta_gastos_pago_fraccionado_aggregation binding would otherwise be silently
        # dropped (no-silent-under-declaration). Calculate still succeeds; the
        # operator sees the unrouted expense instead of an under-declared form.
        unrouted = unsupported_ledger_renta_gastos_pago_fraccionado_observations(
            context.revision, aggregation.observations
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(
                context.revision,
                aggregation.observations,
            ),
            source_transaction_ids=tuple(
                sorted(observation.transaction_id for observation in aggregation.observations),
            ),
            diagnostics=_out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable renta gasto observation (target_casilla_id="
                        f"{observation.target_casilla_id!r}, deductible_amount={observation.deductible_amount}) "
                        f"is not consumed by any ledger_renta_gastos_pago_fraccionado_aggregation binding on revision "
                        f"{context.revision.id!r}; its deductible expense is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
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
    prorrata_apportionment: IvaLedgerProrrataApportionment | None,
) -> tuple[Invoice, ...]:
    """Refuse M303 when domestic invoice IVA would be absent from ledger totals.

    Modelo 303's domestic IVA boxes are sourced from ``ledger_iva_aggregation``:
    the transaction ledger is the filing authority. A bucket can also carry real
    invoice catalogue evidence, but there is no domestic-IVA invoice binding
    family for M303. If positive Spanish invoice IVA exists for the same period
    and its standard domestic cuota would exceed the transaction-ledger cuota
    that the filing is about to use, calculating a zero/subtotal filing would
    silently under-declare. Refuse and require the operator to link/classify the
    transactions that feed the canonical ledger path.

    Returns:
        The invoices whose domestic IVA was compared against the ledger, so the
        caller can disclose how their period placement was arrived at. Empty
        when the screen does not apply or found nothing to compare.
    """
    if str(context.modelo) != Modelo.M303.value:
        return ()
    invoice_observations, invoice_ids, compared_invoices = _m303_standard_domestic_invoice_iva_observations(
        context=context,
        period=period,
        invoice_repository=invoice_repository,
    )
    if not invoice_observations:
        return ()
    invoice_binding_values = resolve_iva_ledger_binding_values(
        context.revision,
        invoice_observations,
        prorrata_apportionment=prorrata_apportionment,
    )
    missing_binding_values = {
        binding_id: invoice_value - transaction_value
        for binding_id in _M303_STANDARD_DOMESTIC_IVA_CUOTA_BINDINGS
        if (invoice_value := invoice_binding_values.get(binding_id, Decimal("0")))
        > (transaction_value := transaction_binding_values.get(binding_id, Decimal("0")))
    }
    if not missing_binding_values:
        return compared_invoices
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
) -> tuple[tuple[IvaLedgerObservation, ...], tuple[str, ...], tuple[Invoice, ...]]:
    try:
        repository = invoice_repository or InvoiceCatalogueRepository(bucket_id=context.bucket_id)
        catalogue = repository.load()
    except _STORAGE_DEGRADATION_ERRORS:
        return (), (), ()
    observations: list[IvaLedgerObservation] = []
    invoice_ids: set[str] = set()
    compared_invoices: list[Invoice] = []
    for invoice in catalogue.values():
        if not _m303_standard_domestic_invoice_in_period(invoice, context=context, period=period):
            continue
        # The date the observation carries must be the date it was SELECTED on,
        # or the record would state one quarter while being declared in another.
        devengo = resolve_invoice_devengo(invoice)
        contributed = False
        for line_index, line in enumerate(invoice.lines):
            if line.iva_amount <= Decimal("0"):
                continue
            observations.append(
                invoice_line_to_iva_observation(
                    invoice_id=f"invoice:{invoice.invoice_id}:{line_index}",
                    issued_at=devengo.devengo_date,
                    invoice_kind=invoice.kind,
                    iva_rate=line.iva_rate,
                    base_amount=line.subtotal,
                    iva_amount=line.iva_amount,
                ),
            )
            invoice_ids.add(invoice.invoice_id)
            contributed = True
        if contributed:
            compared_invoices.append(invoice)
    return tuple(observations), tuple(invoice_ids), tuple(compared_invoices)


def _m303_standard_domestic_invoice_in_period(
    invoice: Invoice,
    *,
    context: CalculationSourceContext,
    period: Period,
) -> bool:
    return (
        invoice.bucket_id == context.bucket_id
        and invoice_devengo_in_period(invoice, period=period)
        and invoice.counterparty_country.strip().upper() == "ES"
    )


def _out_of_window_summary_diagnostics(
    summary: OutOfWindowTransactionSummary | None,
    *,
    source_kind: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    if summary is None:
        return ()
    return (
        out_of_window_summary_source_diagnostic(
            source_kind=source_kind,
            resolver_id=resolver_id,
            count=summary.count,
            min_filing_date=summary.min_filing_date,
            max_filing_date=summary.max_filing_date,
        ),
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


def _iva_prorrata_apportionment_provenance(
    revision: ModeloRevision,
    period: Period,
    apportionment: IvaLedgerProrrataApportionment | None,
) -> tuple[CalculationSourceProvenance, ...]:
    if apportionment is None:
        return ()
    casillas = _iva_deducible_cuota_casillas(revision)
    return (
        CalculationSourceProvenance(
            source_kind="ledger_iva_aggregation",
            source_ref=_iva_prorrata_apportionment_source_ref(period, apportionment),
            legal_refs=tuple(dict.fromkeys(ref for casilla in casillas for ref in casilla.legal_refs)),
            source_refs=tuple(dict.fromkeys(ref for casilla in casillas for ref in casilla.source_refs)),
        ),
    )


def _iva_prorrata_apportionment_source_ref(
    period: Period,
    apportionment: IvaLedgerProrrataApportionment,
) -> str:
    source_ref = (
        f"prorrata-apportionment:{period.filing_year}:{apportionment.regime.value}:"
        f"percentage:{apportionment.percentage}:provenance:{apportionment.provenance.value}"
    )
    if apportionment.source_observation_ref is not None:
        source_ref = f"{source_ref}:source-observation:{apportionment.source_observation_ref}"
    return source_ref


def _iva_deducible_cuota_casillas(revision: ModeloRevision) -> tuple[CasillaDefinition, ...]:
    ledger_iva_amount_bindings = {
        binding.id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_IVA_AGGREGATION
        and getattr(binding.selector, "fact", "iva_amount_sum") == "iva_amount_sum"
    }
    return tuple(
        casilla
        for casilla in revision.casillas
        if "deducible" in casilla.section
        and any(
            binding_id is not None and binding_id in ledger_iva_amount_bindings
            for binding_id in (casilla.binding, *casilla.alternate_bindings)
        )
    )


def _revision_has_binding_source(revision: ModeloRevision, source: str) -> bool:
    return any(binding.source == source for binding in revision.bindings)


def _empty_source_resolution(
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    return CalculationSourceResolution(resolver_id=resolver_id, owned_sources=owned_sources)


#: The ONE canonical retenciones aggregation dispatch: every retenciones modelo
#: mapped to its validated per-perceptor aggregator. This single table is shared by
#: BOTH the live calculate mesh (:meth:`RetencionesAggregationSourceResolver.resolve`)
#: and the per-modelo aggregation service (:func:`~._service.aggregate_per_modelo`,
#: the CLI ``aggregate`` / pull surface), so the two paths cannot drift
#: (``one-aggregation-path-pull-equals-calculate``).
#:
#: The calculate path is scoped to the modelos whose registry declares a
#: ``retenciones_aggregation`` binding (111/115/180/193 today) by the resolver's
#: binding-guard (:func:`_revision_has_binding_source`), NOT by membership of this
#: table — so the scoping tracks the registry, not a hand-maintained sub-list.
#: Modelo 115 uses the quarterly URBAN_RENTAL aggregate for casillas 01/02; modelos
#: 180/193 use the annual aggregate for the distinct-NIF perceptor count (their
#: monetary totals remain on relation-prefill). Modelos 123 and 190 declare no
#: ``retenciones_aggregation`` binding, so they never resolve on the calculate path;
#: they are pull/service-only here. Modelo 190's calculate-path count is
#: "percepciones", a distinct perceptor/clave/subclave figure handled by
#: :class:`~._withholding_source.WithholdingSourceResolver`.
_RETENCIONES_AGGREGATORS = {
    Modelo.M111.value: aggregate_retenciones_111,
    Modelo.M115.value: aggregate_retenciones_115,
    Modelo.M123.value: aggregate_retenciones_123,
    Modelo.M180.value: aggregate_retenciones_180,
    Modelo.M190.value: aggregate_retenciones_190,
    Modelo.M193.value: aggregate_retenciones_193,
}


class RetencionesAggregationSourceResolver:
    """Source mesh resolver for the dedicated per-perceptor retención store.

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

    @staticmethod
    def aggregate(
        modelo: str,
        observations: tuple[RetencionObservation, ...],
        *,
        period: Period,
    ) -> RetencionesAggregation:
        """Aggregate per-perceptor retención observations for ``modelo``.

        The ONE canonical retenciones aggregation entry point. Both this
        resolver's live calculate path (:meth:`resolve`) and the per-modelo
        aggregation service (:func:`~._service.aggregate_per_modelo`, the CLI
        ``aggregate`` / pull surface) route through this single method over the
        shared :data:`_RETENCIONES_AGGREGATORS` dispatch, so the calculate and
        pull surfaces produce byte-identical aggregation and cannot drift
        (``one-aggregation-path-pull-equals-calculate``). Raises ``KeyError``
        for a non-retenciones modelo, matching the prior service dispatch.
        """
        return _RETENCIONES_AGGREGATORS[modelo](tuple(observations), period=period)

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "retenciones_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)
        if str(context.modelo) not in _RETENCIONES_AGGREGATORS:
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
            suggestion = (
                "Supply the per-perceptor retención observations "
                "(`aeat app modelo aggregate --retencion-observation`) before calculating."
            )
            if str(context.modelo) == Modelo.M111.value:
                suggestion = (
                    "Supply the per-perceptor retención observations "
                    "(`aeat app modelo aggregate --retencion-observation`) if any renta subject to "
                    "retención or ingreso a cuenta was paid. If none was paid, do not file an all-blank "
                    "Modelo 111; record the no-obligation period with "
                    f"`aeat config profile edit PROFILE --quiet --modelo-111-no-retenciones-periods "
                    f"{context.filing_year}:{context.period.registry_token}` before verifying M190."
                )
            raise AggregationValidationError(
                t("aggregation.retenciones.errors.perceptor_observations_missing"),
                context={
                    "modelo": str(context.modelo),
                    "filing_year": str(context.filing_year),
                    "period": context.period.registry_token,
                    "source_kind": "retenciones_aggregation",
                },
                suggestion=suggestion,
            )
        aggregation = self.aggregate(str(context.modelo), tuple(observations), period=context.period)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_retenciones_aggregation_binding_values(context.revision, aggregation),
            diagnostics=administrador_retencion_rate_advisory_observations(observations),
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
            source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
            source_ref=f"transaction:{observation.transaction_id}",
        ),
    ]
    if observation.invoice_id is not None:
        provenance.append(
            CalculationSourceProvenance(
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                source_ref=f"purchase-invoice-evidence:{observation.invoice_id}",
            ),
        )
    return tuple(provenance)


__all__ = [
    "LedgerIvaAggregationSourceResolver",
    "LedgerRentaGastosEstimacionDirectaAggregationSourceResolver",
    "LedgerRentaGastosPagoFraccionadoAggregationSourceResolver",
    "LedgerRentaIncomeAggregationSourceResolver",
    "aggregation_period_for_modelo",
]
