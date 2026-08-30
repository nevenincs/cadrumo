"""Modelo 369 OSS/IOSS source-mesh resolver and candidate validator.

The ``ledger_oss_aggregation`` source reads OSS/IOSS-tagged issued invoices
through the bucket's :class:`~domain.invoices.InvoiceCatalogueRepositoryProtocol`
and projects them into substrate-classified :class:`OssIossLedgerCandidate`
rows. Pre-classified callers can also pass candidates directly. Each candidate
is validated against the destination Member State's published IVA rate through
:func:`domain.iva.lookup_rate` and becomes a registry-ready
:class:`~domain.calculations.registry.OssIossLedgerObservation`.

Per the OSS / IOSS regulation suite, the IVA amount on each line MUST
match the destination Member State's published rate for the chosen
rate tier on the supply date. A persisted IVA amount that disagrees
with the lookup is a data-quality blocker: the wrapper rejects it
before the registry resolver sees it, so calculation revisions never
land on inconsistent ledger facts.

The :class:`OssIossLedgerSourceResolver` returns a
:class:`~._source_mesh.CalculationSourceResolution` with resolved binding values,
transaction provenance, and non-blocking diagnostics for empty live catalogues or
declarable OSS observations that no ``ledger_oss_aggregation`` binding consumes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Annotated, ClassVar

from pydantic import BaseModel, Field, StringConstraints

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage import ClassificationError, DecryptionError, EnvelopeVersionError
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.money import CENT, round_to_cents
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.ledger_bindings import (
    OssIossLedgerObservation,
    resolve_ledger_oss_aggregation_binding_values,
    unsupported_ledger_oss_observations,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.invoices.enums import iva_rate_kind
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva.classification import InvoiceKind, TransactionKind
from ...domain.iva.lookup import lookup_rate
from ...domain.iva.oss import OssIossRegime
from ...domain.iva.schema import EUMemberState, IvaRateKind
from ._invoice_devengo import (
    devengo_proxy_attribution_diagnostics,
    invoice_devengo_in_period,
    resolve_invoice_devengo,
)
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from .errors import AggregationValidationError, t

_LedgerId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class OssIossLedgerCandidate(BaseModel):
    """One un-validated ledger line tagged with substrate classification.

    The candidate is the application-layer hand-off shape: a ledger
    line carrying the four classification axes the Modelo 369 binding
    selectors require, plus the base and IVA amounts the bucket
    persists. The :func:`validate_oss_ioss_observation` function
    turns a candidate into a registry-ready
    :class:`OssIossLedgerObservation` once the persisted IVA amount
    has been checked against the destination MS rate.

    Attributes:
        ledger_id: Stable id of the source ledger line.
        transaction_date: When the supply takes place. Drives the rate
            lookup.
        regime: OSS / IOSS Esquema the line is filed under.
        destination_member_state: Member State of consumption per the
            OSS / IOSS place-of-supply rules.
        rate_kind: Substrate rate tier (general / reduced / etc.).
        invoice_direction: Whether the autónomo issued or received the
            invoice.
        transaction_kind: Substrate
            :class:`domain.iva.TransactionKind` the line resolves
            to.
        base_amount: Taxable base in EUR. Must be non-negative.
        iva_amount: IVA amount in EUR persisted on the ledger. Must
            be non-negative.
    """

    model_config = STRICT_FROZEN_CONFIG

    ledger_id: _LedgerId
    transaction_date: date
    regime: OssIossRegime
    destination_member_state: EUMemberState
    rate_kind: IvaRateKind
    invoice_direction: InvoiceKind
    transaction_kind: TransactionKind
    base_amount: Decimal = Field(ge=Decimal("0"))
    iva_amount: Decimal = Field(ge=Decimal("0"))


#: Tolerance applied when comparing a persisted IVA amount against the
#: amount derived from ``base_amount * lookup_rate(...) / 100``.
#:
_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)


def _expected_iva_amount(candidate: OssIossLedgerCandidate) -> Decimal:
    """Return the IVA amount derived from the candidate's base and rate.

    Looks up the destination Member State's rate for the candidate's
    rate tier on the supply date, multiplies by ``base_amount``, and
    rounds to two decimal places — the precision at which ledger
    amounts are persisted.

    Args:
        candidate: The substrate-classified ledger line whose base amount
            and rate kind are used to derive the expected IVA amount.

    Returns:
        The expected IVA amount rounded to two decimal places.
    """
    rate = lookup_rate(
        candidate.destination_member_state,
        candidate.rate_kind,
        candidate.transaction_date,
    )
    derived = candidate.base_amount * rate.pct / Decimal("100")
    return round_to_cents(derived)


def validate_oss_ioss_observation(
    candidate: OssIossLedgerCandidate,
) -> OssIossLedgerObservation:
    """Validate ``candidate`` and return the registry-ready observation.

    Looks up the destination Member State's rate at the supply date,
    derives the expected IVA amount from ``base_amount`` and the
    looked-up rate, and rejects the candidate if the persisted
    ``iva_amount`` deviates from the derived value by more than
    ``CENT``.

    Args:
        candidate: The substrate-classified ledger line to validate.

    Returns:
        A registry-ready :class:`OssIossLedgerObservation` carrying
        the same identifier, supply date, classification axes, base
        amount, and persisted IVA amount as the candidate.

    Raises:
        AggregationValidationError: When the persisted IVA amount
            disagrees with the destination MS rate by more than the
            one-cent tolerance.
    """
    expected = _expected_iva_amount(candidate)
    persisted = round_to_cents(candidate.iva_amount)
    # Ledger amounts are rounded to two decimal places at persistence time, so a
    # difference of one cent or less is rounding noise rather than a data-quality
    # blocker. Larger gaps fail validation and the line is rejected before the
    # registry resolver aggregates it. The quantum is CENT because it is the same
    # cent the rounding produced, not a threshold this module chose.
    if abs(persisted - expected) > CENT:
        raise AggregationValidationError(
            t("aggregation.oss_ioss.errors.iva_amount_mismatches_destination_rate"),
            context={
                "ledger_id": candidate.ledger_id,
                "destination_member_state": candidate.destination_member_state.value,
                "rate_kind": candidate.rate_kind.value,
                "transaction_date": candidate.transaction_date.isoformat(),
                "base_amount": str(candidate.base_amount),
                "persisted_iva_amount": str(persisted),
                "expected_iva_amount": str(expected),
            },
        )
    return OssIossLedgerObservation(
        ledger_id=candidate.ledger_id,
        transaction_date=candidate.transaction_date,
        regime=candidate.regime,
        destination_member_state=candidate.destination_member_state,
        rate_kind=candidate.rate_kind,
        invoice_direction=candidate.invoice_direction,
        transaction_kind=candidate.transaction_kind,
        base_amount=candidate.base_amount,
        iva_amount=candidate.iva_amount,
    )


def validate_oss_ioss_observations(
    candidates: Iterable[OssIossLedgerCandidate],
) -> tuple[OssIossLedgerObservation, ...]:
    """Validate every candidate; raise on the first failure.

    Args:
        candidates: The substrate-classified ledger lines to validate.

    Returns:
        A tuple of registry-ready
        :class:`OssIossLedgerObservation` records in input order.
    """
    return tuple(validate_oss_ioss_observation(candidate) for candidate in candidates)


def aggregate_oss_ioss_bindings(
    revision: ModeloRevision,
    candidates: Sequence[OssIossLedgerCandidate],
) -> dict[BindingId, Decimal]:
    """Validate candidates then resolve every ``ledger_oss_aggregation`` binding.

    Pipeline:

    1. Each candidate is validated through
       :func:`validate_oss_ioss_observation`, which checks the
       persisted IVA against the destination MS rate.
    2. The validated observations are handed off to the registry's
       :func:`resolve_ledger_oss_aggregation_binding_values`
       resolver, which filters by every binding's selector and
       aggregates the matched lines.

    Args:
        revision: The Modelo 369 :class:`ModeloRevision` whose
            ``ledger_oss_aggregation`` bindings should be resolved.
        candidates: Substrate-classified ledger lines for the period.

    Returns:
        A mapping from each binding id on the revision to its
        aggregated Decimal value.
    """
    observations = validate_oss_ioss_observations(candidates)
    return resolve_ledger_oss_aggregation_binding_values(revision, observations)


def _exterior_detail_binding_values(
    revision: ModeloRevision,
    observations: Sequence[OssIossLedgerObservation],
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str]]:
    """Project Exterior service rows from validated invoice observations.

    The record-design bindings are generated from AEAT's positional workbook,
    so discover their semantic field names from the revision instead of
    duplicating generated binding ids here.  One row represents one
    destination/rate tier; repeated invoice lines in that tier are summed.
    """
    if revision.id != "esquema-exterior":
        return {}, {}
    grouped: dict[tuple[EUMemberState, IvaRateKind], list[OssIossLedgerObservation]] = defaultdict(list)
    for observation in observations:
        if (
            observation.regime is OssIossRegime.EXTERNAL_SCHEME
            and observation.transaction_kind is TransactionKind.EXTERNAL_SCHEME_SERVICES
        ):
            if observation.rate_kind not in {IvaRateKind.GENERAL, IvaRateKind.REDUCED}:
                raise AggregationValidationError(
                    t("aggregation.oss_ioss.errors.exterior_rate_kind_unsupported"),
                    context={
                        "ledger_id": observation.ledger_id,
                        "rate_kind": observation.rate_kind.value,
                    },
                )
            grouped[(observation.destination_member_state, observation.rate_kind)].append(observation)
    decimal_values: dict[BindingId, Decimal] = {}
    enum_values: dict[BindingId, str] = {}
    rate_codes = {
        IvaRateKind.GENERAL: "S",
        IvaRateKind.REDUCED: "R",
    }
    for row, ((country, rate_kind), rows) in enumerate(sorted(grouped.items(), key=lambda item: item[0]), start=1):
        rate = lookup_rate(country, rate_kind, rows[0].transaction_date).pct
        fields = {
            f"3-prestaciones-de-servicios-codigo-de-pais-em-de-consumo-{row}": country.name,
            f"3-prestaciones-de-servicios-tipo-iva-{row}": rate_codes[rate_kind],
        }
        decimals = {
            f"3-prestaciones-de-servicios-tipo-de-iva-{row}": rate,
            f"3-prestaciones-de-servicios-base-imponible-{row}": sum((item.base_amount for item in rows), Decimal("0")),
            f"3-prestaciones-de-servicios-cuota-iva-{row}": sum((item.iva_amount for item in rows), Decimal("0")),
        }
        for binding in revision.bindings:
            selector = binding.selector
            if getattr(selector, "record", None) != "modelo-369-exterior-t36901":
                continue
            field = getattr(selector, "field", None)
            if field in fields:
                enum_values[binding.id] = fields[field]
            elif field in decimals:
                decimal_values[binding.id] = decimals[field]
    return decimal_values, enum_values


def _candidate_for_invoice_line(
    invoice: Invoice,
    line: InvoiceLine,
    *,
    line_index: int,
    devengo_date: date,
) -> OssIossLedgerCandidate | None:
    """Project one invoice line into an OSS/IOSS candidate, or ``None`` when not applicable.

    The regime / destination checks mean the line is not an OSS/IOSS
    operation at all -- correctly silent, nothing to declare. A line that
    passes both IS a real, declarable OSS/IOSS operation, so a missing
    rate_kind or a missing euro conversion from that point on REFUSES rather
    than silently drops it: by operator ruling ("aim for explicit red
    signals... until schema and api converges"), a would-be-silently-dropped
    declarable line is a hard stop, not an advisory beside a smaller-but-green
    figure.
    """
    if invoice.oss_ioss_regime is None or invoice.oss_transaction_kind is None:
        return None
    destination = invoice.counterparty_eu_member_state
    if destination is None:
        return None
    rate_kind = line.oss_rate_kind or iva_rate_kind(line.iva_rate)
    if rate_kind is None:
        raise AggregationValidationError(
            t("aggregation.oss_ioss.errors.invoice_line_rate_kind_unclassifiable"),
            context={
                "invoice_id": invoice.invoice_id,
                "invoice_number": invoice.invoice_number,
                "line_index": str(line_index),
                "iva_rate": str(line.iva_rate.value),
            },
        )
    # OSS/IOSS is cross-border EU B2C by definition, where invoicing in the
    # destination Member State's own currency (PLN, SEK, DKK, HUF, CZK, RON,
    # BGN...) is the ORDINARY case, not an edge case. line.subtotal /
    # line.iva_amount are native to invoice.currency (InvoiceLine carries no
    # currency of its own); base_amount/iva_amount on the candidate are
    # documented as EUR, so this converts through the same fx_rate resolution
    # the invoice-level totals already use (line_amount_eur) rather than the
    # invoice-line's raw native fields.
    base_amount_eur = invoice.line_amount_eur(line.subtotal)
    iva_amount_eur = invoice.line_amount_eur(line.iva_amount)
    if base_amount_eur is None or iva_amount_eur is None:
        raise AggregationValidationError(
            t("aggregation.oss_ioss.errors.invoice_line_currency_unconverted"),
            context={
                "invoice_id": invoice.invoice_id,
                "invoice_number": invoice.invoice_number,
                "currency": invoice.currency,
                "line_index": str(line_index),
            },
        )
    return OssIossLedgerCandidate(
        ledger_id=f"{invoice.invoice_id}:{line_index}",
        transaction_date=devengo_date,
        regime=invoice.oss_ioss_regime,
        destination_member_state=destination,
        rate_kind=rate_kind,
        invoice_direction=invoice.kind,
        transaction_kind=invoice.oss_transaction_kind,
        base_amount=base_amount_eur,
        iva_amount=iva_amount_eur,
    )


class OssIossInvoiceProjection(BaseModel):
    """The Modelo 369 candidates for a period, beside the invoices they came from.

    The invoices ride along because the candidate cannot answer for its own
    provenance: it carries a resolved devengo date but not whether that date
    was declared or substituted, and the advisory the resolver owes the
    operator is about exactly that distinction.

    Attributes:
        candidates: The substrate-classified OSS/IOSS ledger lines.
        contributing_invoices: The invoices at least one candidate came from.
    """

    model_config = STRICT_FROZEN_CONFIG

    candidates: tuple[OssIossLedgerCandidate, ...] = ()
    contributing_invoices: tuple[Invoice, ...] = ()


def project_oss_ioss_invoices_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> OssIossInvoiceProjection:
    """Project OSS/IOSS-tagged issued invoices into Modelo 369 ledger candidates.

    Attribution is by the LIVA art. 75 devengo date through the shared
    :func:`~application.aggregation.invoice_devengo_in_period` predicate, so an
    operation performed in one quarter and invoiced in the next is declared in
    the quarter it was performed, and every path that folds invoices into a
    period answers that question the same way.

    Args:
        bucket_id: Active bucket id for the default invoice repository.
        period: Filing period whose date span filters issued invoices.
        invoice_repository: Optional
            :class:`~domain.invoices.InvoiceCatalogueRepositoryProtocol` used
            instead of the active bucket repository.

    Returns:
        The candidates for the period beside the invoices they were projected
        from.
    """
    projection_period = period
    if period.registry_token.startswith("EXT-"):
        projection_period = Period.from_year_and_code(
            period.filing_year,
            period.registry_token.removeprefix("EXT-"),
        )
    if not projection_period.has_date_span():
        return OssIossInvoiceProjection()
    repo = invoice_repository if invoice_repository is not None else InvoiceCatalogueRepository(bucket_id=bucket_id)
    candidates: list[OssIossLedgerCandidate] = []
    contributing: list[Invoice] = []
    for invoice in repo.load():
        if invoice.kind is not InvoiceKind.ISSUED:
            continue
        if not invoice_devengo_in_period(invoice, period=projection_period):
            continue
        devengo_date = resolve_invoice_devengo(invoice).devengo_date
        projected = [
            candidate
            for index, line in enumerate(invoice.lines, start=1)
            if (candidate := _candidate_for_invoice_line(invoice, line, line_index=index, devengo_date=devengo_date))
            is not None
        ]
        if projected:
            candidates.extend(projected)
            contributing.append(invoice)
    return OssIossInvoiceProjection(candidates=tuple(candidates), contributing_invoices=tuple(contributing))


def oss_ioss_candidates_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> tuple[OssIossLedgerCandidate, ...]:
    """Return only the Modelo 369 candidates for the period.

    The narrow accessor for callers that aggregate but emit no diagnostics.
    Delegates to :func:`project_oss_ioss_invoices_from_repositories` rather
    than repeating its selection, so the two cannot attribute a period
    differently.

    Args:
        bucket_id: Active bucket id for the default invoice repository.
        period: Filing period whose date span filters issued invoices.
        invoice_repository: Optional
            :class:`~domain.invoices.InvoiceCatalogueRepositoryProtocol` used
            instead of the active bucket repository.

    Returns:
        A tuple of :class:`OssIossLedgerCandidate` rows projected from issued
        invoices devengando in the period.
    """
    return project_oss_ioss_invoices_from_repositories(
        bucket_id=bucket_id,
        period=period,
        invoice_repository=invoice_repository,
    ).candidates


def aggregate_oss_ioss_from_repositories(
    revision: ModeloRevision,
    *,
    bucket_id: str,
    period: Period,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> dict[BindingId, Decimal]:
    """Resolve Modelo 369 OSS/IOSS bindings from the live invoice catalogue.

    Args:
        revision: The :class:`ModeloRevision` whose OSS/IOSS bindings are resolved.
        bucket_id: Active bucket id for the default invoice repository.
        period: Filing period whose date span filters issued invoices.
        invoice_repository: Optional
            :class:`~domain.invoices.InvoiceCatalogueRepositoryProtocol` used
            instead of the active bucket repository.
    """
    return aggregate_oss_ioss_bindings(
        revision,
        oss_ioss_candidates_from_repositories(
            bucket_id=bucket_id,
            period=period,
            invoice_repository=invoice_repository,
        ),
    )


class OssIossLedgerSourceResolver:
    """Source mesh resolver for Modelo 369 OSS / IOSS ledger candidates."""

    resolver_id: ClassVar[str] = "ledger_oss_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_OSS_AGGREGATION,)

    def __init__(
        self,
        *,
        candidates: Sequence[OssIossLedgerCandidate] | None = None,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    ) -> None:
        """Construct the resolver with a pre-classified ledger candidate sequence.

        Args:
            candidates: The substrate-classified ledger lines for the
                current period. The resolver validates and aggregates
                these on each :meth:`resolve` call.
            invoice_repository: Optional live invoice repository port used to
                project OSS/IOSS-tagged invoices when ``candidates`` is not
                supplied.
        """
        self._candidates = tuple(candidates) if candidates is not None else None
        self._invoice_repository = invoice_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Validate candidates and return the resolved OSS/IOSS binding values.

        Validates every candidate through :func:`validate_oss_ioss_observation`
        then delegates to the registry's
        ``resolve_ledger_oss_aggregation_binding_values`` to aggregate the
        matched lines per binding selector.

        When the resolver is constructed with explicit ``candidates``, those
        candidates are folded directly. When ``candidates`` is omitted, the live
        operator path projects OSS/IOSS-tagged issued invoices from the invoice
        repository into candidates first. If no candidate is available, the
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
            projection = (
                project_oss_ioss_invoices_from_repositories(
                    bucket_id=context.bucket_id,
                    period=context.period,
                    invoice_repository=self._invoice_repository,
                )
                if self._candidates is None
                else OssIossInvoiceProjection(candidates=self._candidates)
            )
            candidates = projection.candidates
        except _STORAGE_DEGRADATION_ERRORS as exc:
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
                diagnostics=self._no_live_source_diagnostics(context),
            )
        observations = validate_oss_ioss_observations(candidates)
        exterior_values, exterior_enum_values = _exterior_detail_binding_values(context.revision, observations)
        # Fail-closed advisory parity with the IVA screen: a non-zero declarable
        # OSS line whose classification tuple matches no ledger_oss_aggregation
        # binding would otherwise be silently dropped (no-silent-under-declaration).
        unrouted = unsupported_ledger_oss_observations(context.revision, observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values={
                **resolve_ledger_oss_aggregation_binding_values(context.revision, observations),
                **exterior_values,
            },
            enum_binding_values=exterior_enum_values,
            source_transaction_ids=tuple(
                sorted({observation.ledger_id.split(":", 1)[0] for observation in observations}),
            ),
            diagnostics=devengo_proxy_attribution_diagnostics(
                projection.contributing_invoices,
                source_kind="ledger_oss_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_oss_aggregation",
                    resolver_id=self.resolver_id,
                    source_ref=f"transaction:{observation.ledger_id}",
                    message=(
                        f"declarable OSS observation {observation.ledger_id!r} "
                        f"(regime={observation.regime.value!r}, "
                        f"destination={observation.destination_member_state.value!r}, "
                        f"rate_kind={observation.rate_kind.value!r}, "
                        f"invoice_direction={observation.invoice_direction.value!r}, "
                        f"transaction_kind={observation.transaction_kind.value!r}) is not consumed by any "
                        f"ledger_oss_aggregation binding on revision {context.revision.id!r}; "
                        "its base/cuota is not declared on this calculation"
                    ),
                )
                for observation in unrouted
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
                )
                for observation in observations
            ),
        )

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
    "OssIossInvoiceProjection",
    "OssIossLedgerCandidate",
    "OssIossLedgerSourceResolver",
    "aggregate_oss_ioss_bindings",
    "aggregate_oss_ioss_from_repositories",
    "oss_ioss_candidates_from_repositories",
    "project_oss_ioss_invoices_from_repositories",
    "validate_oss_ioss_observation",
    "validate_oss_ioss_observations",
]
