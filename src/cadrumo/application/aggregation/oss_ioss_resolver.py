"""Source mesh resolver for Modelo 369 OSS and IOSS ledger candidates and their projection from issued invoices.

This module uses :class:`InvoiceCatalogue`, the profile's invoice catalogue.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import content_hash_hex
from ...core.i18n.translatable import Translatable as tr
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.ledger_oss_bindings import (
    OssIossLedgerObservation,
    OssLineEffect,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.currency.errors import ExchangeRateProviderError
from ...domain.currency.models import EurRateLookupStatus
from ...domain.currency.service import published_eur_rate_on_day_or_next_publication
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.enums import iva_rate_kind
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.lookup import lookup_rate
from ...domain.iva.schema import InvoiceKind
from ..exchange_rate_provider import exchange_rate_provider
from ..invoices.catalogue_reads_ports import (
    BucketBoundCatalogueReader,
    InvoiceCatalogueReadPersistenceError,
    InvoiceCatalogueReadPorts,
)
from ..invoices.source_observations import is_rectificativa, rectified_invoices
from .errors import AggregationValidationError
from .invoice_devengo import (
    devengo_proxy_attribution_diagnostics,
    invoice_devengo_in_period,
    resolve_invoice_devengo,
)
from .oss_ioss import (
    OssIossInvoiceProjection,
    OssIossLedgerCandidate,
    aggregate_oss_ioss_bindings,
    closed_detail_record_rows,
    correction_binding_values,
    detail_binding_values,
    observations_at_row_level,
    observations_without_detail_row,
    period_holding,
    projection_period,
    refuse_rate_chosen_by_issue_date,
    row_level_binding_values,
    validate_oss_ioss_observations,
)
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import source_context_operation, storage_degradation_resolution


def candidate_for_invoice_line(
    invoice: Invoice,
    line: InvoiceLine,
    *,
    line_index: int,
    devengo_date: date,
    period_last_day: date,
    effect: OssLineEffect = OssLineEffect.SUPPLY,
) -> OssIossLedgerCandidate | None:
    """Project one invoice line into an OSS/IOSS candidate, or ``None`` when not applicable.

    The regime / destination checks mean the line is not an OSS/IOSS
    operation at all -- correctly silent, nothing to declare. A line that
    passes both IS a real, declarable OSS/IOSS operation, so a missing
    rate_kind or a missing period-close rate from that point on REFUSES rather
    than silently drops it. A would-be-silently-dropped declarable line is a
    hard stop, not an advisory beside a smaller-but-green figure.
    """
    if invoice.oss_ioss_regime is None or invoice.oss_transaction_kind is None:
        return None
    destination = invoice.counterparty_eu_member_state
    if destination is None:
        return None
    rate_kind = line.oss_rate_kind or iva_rate_kind(line.iva_rate, devengo_date)
    if rate_kind is None:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.invoice_line_rate_kind_unclassifiable"),
            context={
                "invoice_id": invoice.invoice_id,
                "invoice_number": invoice.invoice_number,
                "line_index": str(line_index),
                "iva_rate": line.iva_rate.value,
            },
        )
    # OSS/IOSS is cross-border B2C, where invoicing in the destination's own
    # currency is the ordinary case. Art. 163 noniesdecies, duovicies and
    # septvicies fix one rate for the whole return, the period's last day (or the
    # next day of publication when none is published that day), so the rate
    # stamped on the invoice at its operation date does not apply here.
    rate = _period_close_rate(invoice, line_index=line_index, last_day=period_last_day)
    return OssIossLedgerCandidate(
        ledger_id=f"{invoice.invoice_id}:{line_index}",
        transaction_date=devengo_date,
        regime=invoice.oss_ioss_regime,
        destination_member_state=destination,
        rate_kind=rate_kind,
        invoice_direction=invoice.kind,
        transaction_kind=invoice.oss_transaction_kind,
        # Left unrounded: the return states totals per state and rate, so cents are taken at the row.
        base_amount=line.subtotal if rate is None else line.subtotal * rate,
        iva_amount=line.iva_amount if rate is None else line.iva_amount * rate,
        effect=effect,
    )


def _period_close_rate(invoice: Invoice, *, line_index: int, last_day: date) -> Decimal | None:
    """Return the ECB rate the return converts this invoice at, or ``None`` for a euro invoice."""
    if invoice.currency == DEFAULT_CURRENCY:
        return None
    context = {
        "invoice_id": invoice.invoice_id,
        "invoice_number": invoice.invoice_number,
        "currency": invoice.currency,
        "line_index": str(line_index),
        "rate_date": last_day.isoformat(),
    }
    try:
        lookup = published_eur_rate_on_day_or_next_publication(
            invoice.currency, last_day, rate_provider=exchange_rate_provider()
        )
    except ExchangeRateProviderError as exc:
        # An unreachable authority answers nothing about the rate: the same refusal, never a default.
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.invoice_line_currency_unconverted"), context=context
        ) from exc
    if lookup.status is not EurRateLookupStatus.FOUND or lookup.rate is None:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.invoice_line_currency_unconverted"), context=context
        )
    return lookup.rate


def _rectificativas_naming(target: Invoice, catalogue: InvoiceCatalogue, projection_period: Period) -> list[Invoice]:
    """Return the rectificativas issued by the period's end that name ``target``."""
    return [
        other
        for other in catalogue.values()
        if is_rectificativa(other)
        and other.issued_at <= projection_period.end_date
        and target in rectified_invoices(other, catalogue)
    ]


def _refuse_earlier_correction_it_cannot_state(
    invoice: Invoice, target: Invoice, catalogue: InvoiceCatalogue, projection_period: Period
) -> None:
    """Refuse a correction of an earlier period with no sourced euro figure, or above what it names.

    Art. 163 noniesdecies.Uno.c) and siblings convert at the last day of the return's
    period and do not say which period a later correction's foreign amount takes. The
    amounts corrected so far include the earlier rectificativas of the same invoice.
    """
    context = {"invoice_id": invoice.invoice_id, "invoice_number": invoice.invoice_number}
    if invoice.currency != DEFAULT_CURRENCY or target.currency != DEFAULT_CURRENCY:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.correction_currency_unsourced"),
            context={**context, "currency": invoice.currency, "corrected_currency": target.currency},
        )
    named = _rectificativas_naming(target, catalogue, projection_period)
    base = sum((other.base_total for other in named), Decimal("0"))
    cuota = sum((other.iva_total for other in named), Decimal("0"))
    if base > target.base_total or cuota > target.iva_total:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.rectificativa_above_row"),
            context={
                "destination_member_state": str(target.counterparty_eu_member_state),
                "rate": "",
                "net_base": str(target.base_total - base),
                "net_cuota": str(target.iva_total - cuota),
            },
        )


def _corrected_invoice_devengo(
    invoice: Invoice, catalogue: InvoiceCatalogue, projection_period: Period
) -> tuple[date, Period | None]:
    """Return the devengo of the invoice a correction names and, when earlier, the period holding it."""
    context = {"invoice_id": invoice.invoice_id, "invoice_number": invoice.invoice_number}
    candidates = rectified_invoices(invoice, catalogue)
    if len(candidates) > 1:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.rectificativa_target_ambiguous"),
            context=context,
        )
    target = next(iter(candidates), None)
    if target is None:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.rectificativa_target_unknown"),
            context=context,
        )
    if (
        target.oss_ioss_regime != invoice.oss_ioss_regime
        or target.oss_transaction_kind != invoice.oss_transaction_kind
        or target.counterparty_eu_member_state != invoice.counterparty_eu_member_state
    ):
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.rectificativa_target_differs"),
            context=context,
        )
    devengo_date = resolve_invoice_devengo(target).devengo_date
    if invoice_devengo_in_period(target, period=projection_period):
        return devengo_date, None
    if devengo_date > projection_period.end_date:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.rectificativa_target_later"),
            context=context,
        )
    _refuse_earlier_correction_it_cannot_state(invoice, target, catalogue, projection_period)
    return devengo_date, period_holding(devengo_date, projection_period)


def _project_oss_invoice(
    invoice: Invoice, projection_period: Period, catalogue: InvoiceCatalogue
) -> list[OssIossLedgerCandidate]:
    if invoice.kind is not InvoiceKind.ISSUED or invoice.oss_ioss_regime is None:
        return []
    corrects = is_rectificativa(invoice)
    # A correction is made when it is issued, whatever operation date it repeats.
    made_here = (
        projection_period.contains(invoice.issued_at)
        if corrects
        else invoice_devengo_in_period(invoice, period=projection_period)
    )
    if not made_here:
        return []
    devengo_date, corrected_period = (
        _corrected_invoice_devengo(invoice, catalogue, projection_period)
        if corrects
        else (resolve_invoice_devengo(invoice).devengo_date, None)
    )
    return [
        candidate.model_copy(update={"corrected_period": corrected_period})
        for index, line in enumerate(invoice.lines, start=1)
        if (
            candidate := candidate_for_invoice_line(
                invoice,
                line,
                line_index=index,
                devengo_date=devengo_date,
                period_last_day=projection_period.end_date,
                effect=OssLineEffect.CORRECTION if corrects else OssLineEffect.SUPPLY,
            )
        )
        is not None
    ]


def project_oss_ioss_invoices_from_repositories(
    *,
    period: Period,
    ports: InvoiceCatalogueReadPorts,
) -> OssIossInvoiceProjection:
    """Project OSS/IOSS-tagged issued invoices into Modelo 369 ledger candidates.

    Attribution is by the LIVA art. 75 devengo date through the shared
    :func:`~application.aggregation.invoice_devengo.invoice_devengo_in_period` predicate, so an
    operation performed in one quarter and invoiced in the next is declared in
    the quarter it was performed, and every path that folds invoices into a
    period answers that question the same way.

    Args:
        period: Filing period whose date span filters issued invoices.
        ports: Required application-owned catalogue read capabilities for the
            composed profile bucket.

    Returns:
        The candidates for the period beside the invoices they were projected
        from.
    """
    window = projection_period(period)
    if not window.has_date_span():
        return OssIossInvoiceProjection()
    candidates: list[OssIossLedgerCandidate] = []
    contributing: list[Invoice] = []
    catalogue = ports.invoice_reader.load()
    for invoice in catalogue:
        projected = _project_oss_invoice(invoice, window, catalogue)
        if projected:
            candidates.extend(projected)
            contributing.append(invoice)
    source_bucket_id = (
        ports.invoice_reader.bucket_id if isinstance(ports.invoice_reader, BucketBoundCatalogueReader) else None
    )
    return OssIossInvoiceProjection(
        candidates=tuple(candidates),
        contributing_invoices=tuple(contributing),
        source_bucket_id=source_bucket_id,
        catalogue_fingerprint=content_hash_hex(catalogue.model_dump(mode="json"))
        if (source_bucket_id is not None and source_bucket_id)
        else None,
    )


def oss_ioss_candidates_from_repositories(
    *,
    period: Period,
    ports: InvoiceCatalogueReadPorts,
) -> tuple[OssIossLedgerCandidate, ...]:
    """Return only the Modelo 369 candidates for the period.

    The narrow accessor for callers that aggregate but emit no diagnostics.
    Delegates to :func:`project_oss_ioss_invoices_from_repositories` rather
    than repeating its selection, so the two cannot attribute a period
    differently.

    Args:
        period: Filing period whose date span filters issued invoices.
        ports: Required application-owned catalogue read capabilities for the
            composed profile bucket.

    Returns:
        A tuple of :class:`OssIossLedgerCandidate` rows projected from issued
        invoices devengando in the period.
    """
    return project_oss_ioss_invoices_from_repositories(
        period=period,
        ports=ports,
    ).candidates


def aggregate_oss_ioss_from_repositories(
    revision: ModeloRevision,
    *,
    period: Period,
    ports: InvoiceCatalogueReadPorts,
    operation: PinnedAuthorityOperation | None = None,
) -> dict[BindingId, Decimal]:
    """Resolve Modelo 369 OSS/IOSS bindings from the live invoice catalogue.

    Args:
        revision: The :class:`ModeloRevision` whose OSS/IOSS bindings are resolved.
        period: Filing period whose date span filters issued invoices.
        ports: Required application-owned catalogue read capabilities for the
            composed profile bucket.
        operation: Existing generation-pinned authority operation. When omitted,
            one indexed operation is opened at this composition boundary.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_oss_ioss_from_repositories(
                revision,
                period=period,
                ports=ports,
                operation=indexed_operation,
            )
    return aggregate_oss_ioss_bindings(
        revision,
        oss_ioss_candidates_from_repositories(period=period, ports=ports),
        operation=operation,
    )


def _projected_rate_diagnostics(
    observations: Sequence[OssIossLedgerObservation],
    *,
    resolver_id: str,
    operation: PinnedAuthorityOperation,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Warn of each line whose figure rests on a rate the table only projects to its date."""
    return tuple(
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind="ledger_oss_aggregation",
            resolver_id=resolver_id,
            source_ref="rate_date_projected",
            message=(
                f"OSS line {observation.ledger_id!r}: no edition of the {observation.destination_member_state.value} "
                f"{observation.rate_kind.value} rate covers {observation.transaction_date}; its cuota matches "
                f"the nearest edition, {record.pct} %, which is a projection and not a published rate for that date."
            ),
            remedy="Check the rate that applied on the supply date against the Member State's own publication.",
        )
        for observation in observations
        if not (
            record := lookup_rate(
                observation.destination_member_state,
                observation.rate_kind,
                observation.transaction_date,
                operation=operation,
            )
        ).published_on_date
    )


def _unrouted_observation_diagnostics(
    unrouted: Sequence[OssIossLedgerObservation],
    *,
    revision_id: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per declarable observation that no detail table of the revision can take."""
    return tuple(
        CalculationSourceDiagnostic(
            reason="unrouted_observation",
            source_kind="ledger_oss_aggregation",
            resolver_id=resolver_id,
            source_ref=f"transaction:{observation.ledger_id}",
            message=(
                f"This calculation omits base/cuota for OSS line {observation.ledger_id!r} "
                f"(regime={observation.regime.value!r}, "
                f"destination={observation.destination_member_state.value!r}, "
                f"rate_kind={observation.rate_kind.value!r}, "
                f"invoice_direction={observation.invoice_direction.value!r}, "
                f"transaction_kind={observation.transaction_kind.value!r}). "
                f"No detail table on {revision_id!r}; Union goods need a state of dispatch "
                "absent from the invoice, and other regimes need their own revision."
            ),
        )
        for observation in unrouted
    )


class OssIossLedgerSourceResolver:
    """Source mesh resolver for Modelo 369 OSS / IOSS ledger candidates."""

    resolver_id: ClassVar[str] = "ledger_oss_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_OSS_AGGREGATION,)

    def __init__(
        self,
        *,
        ports: InvoiceCatalogueReadPorts,
        candidates: Sequence[OssIossLedgerCandidate] | None = None,
    ) -> None:
        """Construct the resolver with a pre-classified ledger candidate sequence.

        Args:
            candidates: The substrate-classified ledger lines for the
                current period. The resolver validates and aggregates
                these on each :meth:`resolve` call.
            ports: Required application-owned catalogue read capabilities used
                to project OSS/IOSS-tagged invoices when ``candidates`` is not
                supplied.
        """
        self._ports = ports
        self._candidates = tuple(candidates) if candidates is not None else None

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Validate candidates and return the resolved OSS/IOSS binding values.

        Validates every candidate through :func:`validate_oss_ioss_observation`
        then delegates to the registry's
        the registry's ledger OSS aggregation resolver to aggregate the
        matched lines per binding selector.

        When the resolver is constructed with explicit ``candidates``, those
        candidates are folded directly. When ``candidates`` is omitted, the live
        operator path projects OSS/IOSS-tagged issued invoices from the
        application catalogue read capability into candidates first. If no
        candidate is available, the
        resolver still CLAIMS ``ledger_oss_aggregation`` (so the binding
        compiles and is not flagged as a novel source) but surfaces one
        non-blocking ``oss_no_live_source`` advisory per declared OSS binding.
        This keeps a Modelo 369 OSS cuota from resolving to a SILENT
        claimed-zero when the catalogue carries no classifiable OSS invoices.

        Args:
            context: The :class:`CalculationSourceContext` carrying the
                ``ModeloRevision`` whose ``ledger_oss_aggregation`` bindings
                should be resolved.

        Returns:
            A :class:`CalculationSourceResolution` with resolved
            binding values, source transaction ids, and per-observation
            provenance records — or, when no candidates were supplied, an
            empty resolution carrying one ``oss_no_live_source`` advisory per
            declared OSS binding when no candidates can be projected.

        Raises:
            AggregationValidationError: When any candidate's persisted IVA
                amount disagrees with the destination Member State rate by
                more than one cent.
        """
        try:
            with source_context_operation(context) as indexed_operation:
                self._require_source_bucket(context)
                projection = (
                    project_oss_ioss_invoices_from_repositories(
                        period=context.period,
                        ports=self._ports,
                    )
                    if self._candidates is None
                    else OssIossInvoiceProjection(candidates=self._candidates)
                )
                candidates = projection.candidates
                observations = validate_oss_ioss_observations(candidates, operation=indexed_operation)
                refuse_rate_chosen_by_issue_date(
                    context,
                    projection,
                    observations,
                    operation=indexed_operation,
                )
                detail_values, detail_enum_values = detail_binding_values(
                    context.revision,
                    observations,
                    operation=indexed_operation,
                )
                correction_values, correction_enum_values = correction_binding_values(
                    context,
                    observations,
                    operation=indexed_operation,
                )
                detail_values = {**detail_values, **correction_values}
                detail_enum_values = {**detail_enum_values, **correction_enum_values}
                unrouted = observations_without_detail_row(
                    context.revision,
                    observations,
                    operation=indexed_operation,
                )
                at_row_level = observations_at_row_level(observations, operation=indexed_operation)
                closed_rows = (
                    closed_detail_record_rows(
                        context,
                        projection,
                        supplied_binding_ids=frozenset(detail_values) | frozenset(detail_enum_values),
                        operation=indexed_operation,
                    )
                    if not unrouted
                    else ()
                )
        except InvoiceCatalogueReadPersistenceError as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        if not candidates:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                closed_record_row_sets=closed_rows,
                diagnostics=self._no_live_source_diagnostics(context),
            )
        # Fail-closed advisory parity with the IVA screen: a non-zero declarable
        # OSS line that no detail table can take would otherwise be silently
        # dropped (no-silent-under-declaration).
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values={
                **row_level_binding_values(context.revision, at_row_level),
                **detail_values,
            },
            enum_binding_values=detail_enum_values,
            closed_record_row_sets=closed_rows,
            source_transaction_ids=tuple(
                sorted({observation.ledger_id.split(":", 1)[0] for observation in observations}),
            ),
            diagnostics=devengo_proxy_attribution_diagnostics(
                projection.contributing_invoices,
                source_kind="ledger_oss_aggregation",
                resolver_id=self.resolver_id,
            )
            + _projected_rate_diagnostics(observations, resolver_id=self.resolver_id, operation=indexed_operation)
            + _unrouted_observation_diagnostics(
                unrouted, revision_id=context.revision.id, resolver_id=self.resolver_id
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_OSS_AGGREGATION,
                    contributor_source_kind="ledger_oss_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_OSS_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"transaction:{observation.ledger_id}",
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
                )
                for observation in observations
            ),
        )

    def _require_source_bucket(self, context: CalculationSourceContext) -> None:
        if (
            self._candidates is None
            and isinstance(self._ports.invoice_reader, BucketBoundCatalogueReader)
            and self._ports.invoice_reader.bucket_id is not None
            and self._ports.invoice_reader.bucket_id != context.bucket_id
        ):
            raise AggregationValidationError(tr("aggregation.source_mesh.errors.closed_record_rows_unadmitted"))

    def _no_live_source_diagnostics(self, context: CalculationSourceContext) -> tuple[CalculationSourceDiagnostic, ...]:
        """Return one ``oss_no_live_source`` advisory per OSS binding on the revision.

        Surfaced only when the resolver was constructed with no candidates and
        the revision actually declares ``ledger_oss_aggregation`` bindings, so
        a modelo with no OSS bindings produces no spurious advisory.
        """
        return tuple(
            CalculationSourceDiagnostic(
                reason="oss_no_live_source",
                source_kind="ledger_oss_aggregation",
                resolver_id=self.resolver_id,
                binding_id=binding.id,
                message=(
                    f"binding {binding.id!r} declares source 'ledger_oss_aggregation' but no "
                    "OSS/IOSS-tagged issued invoice line was available for the filing period; "
                    "the OSS cuota is NOT auto-computed from the invoice catalogue"
                ),
            )
            for binding in context.revision.bindings
            if str(binding.source) == "ledger_oss_aggregation"
        )


__all__ = [
    "OssIossLedgerSourceResolver",
    "aggregate_oss_ioss_from_repositories",
    "oss_ioss_candidates_from_repositories",
    "project_oss_ioss_invoices_from_repositories",
]
