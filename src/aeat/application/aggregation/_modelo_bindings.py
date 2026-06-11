"""Modelo binding values derived from bucket-local ledger catalogues.

Used by: :mod:`~._service` (per-modelo aggregation provider) to resolve registry bindings.

Accepts a :class:`~aeat.domain.calculations.registry.ModeloRevision` to drive ledger aggregation binding
resolution across IVA, renta income, and renta expense source kinds.
Expense aggregation reads from both a :class:`~aeat.domain.transactions.TransactionCatalogueRepository`
and an :class:`~aeat.domain.invoices.InvoiceCatalogueRepository`; the invoice repository supplies
purchase-invoice evidence that the renta expense pipeline requires.

Related: :mod:`~._iva_ledger`, :mod:`~._renta_ledger`, :mod:`~._renta_income_ledger` for ledger aggregation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from types import MappingProxyType

from pydantic import BaseModel, Field, field_serializer, field_validator

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period, PeriodError
from ...domain.calculations.registry import (
    ModeloRevision,
    resolve_ledger_iva_aggregation_binding_values,
    resolve_ledger_renta_expense_aggregation_binding_values,
    resolve_ledger_renta_income_aggregation_binding_values,
    unsupported_ledger_iva_observations,
)
from ...domain.invoices import InvoiceCatalogueRepositoryProtocol, InvoicePersistenceError
from ...domain.renta import RentaDeductibleExpenseObservation
from ...domain.transactions import TransactionCatalogueRepositoryProtocol, TransactionPersistenceError
from ._errors import AggregationValidationError, t
from ._iva_ledger import (
    IvaLedgerAggregationIssue,
    aggregate_iva_ledger_observations_from_repositories,
)
from ._renta_income_ledger import (
    RentaIncomeLedgerAggregationIssue,
    aggregate_renta_income_ledger_from_repositories,
)
from ._renta_ledger import (
    RentaLedgerAggregationIssue,
    aggregate_renta_ledger_expenses_from_repositories,
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
    TransactionPersistenceError,
)


class ModeloLedgerBindingAggregation(BaseModel):
    """Ledger-derived binding values for one modelo calculation window."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    filing_year: int = Field(ge=2000, le=2100)
    period: str = Field(min_length=1, max_length=16)
    binding_values: Mapping[str, Decimal] = Field(default_factory=dict)
    source_transaction_ids: Sequence[str] = Field(default_factory=tuple)
    iva_issues: Sequence[IvaLedgerAggregationIssue] = Field(default_factory=tuple)
    renta_issues: Sequence[RentaLedgerAggregationIssue] = Field(default_factory=tuple)
    renta_income_issues: Sequence[RentaIncomeLedgerAggregationIssue] = Field(default_factory=tuple)

    @field_validator("binding_values")
    @classmethod
    def _freeze_binding_values(cls, value: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_validator("source_transaction_ids")
    @classmethod
    def _freeze_source_transaction_ids(cls, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("iva_issues")
    @classmethod
    def _freeze_iva_issues(
        cls,
        value: Sequence[IvaLedgerAggregationIssue],
    ) -> tuple[IvaLedgerAggregationIssue, ...]:
        return tuple(value)

    @field_validator("renta_issues")
    @classmethod
    def _freeze_renta_issues(
        cls,
        value: Sequence[RentaLedgerAggregationIssue],
    ) -> tuple[RentaLedgerAggregationIssue, ...]:
        return tuple(value)

    @field_serializer("binding_values")
    def _serialize_binding_values(self, value: Mapping[str, Decimal]) -> dict[str, Decimal]:
        return dict(value)

    @field_serializer("source_transaction_ids")
    def _serialize_source_transaction_ids(self, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(value)

    @field_serializer("iva_issues")
    def _serialize_iva_issues(
        self,
        value: Sequence[IvaLedgerAggregationIssue],
    ) -> tuple[IvaLedgerAggregationIssue, ...]:
        return tuple(value)

    @field_validator("renta_income_issues")
    @classmethod
    def _freeze_renta_income_issues(
        cls,
        value: Sequence[RentaIncomeLedgerAggregationIssue],
    ) -> tuple[RentaIncomeLedgerAggregationIssue, ...]:
        return tuple(value)

    @field_serializer("renta_issues")
    def _serialize_renta_issues(
        self,
        value: Sequence[RentaLedgerAggregationIssue],
    ) -> tuple[RentaLedgerAggregationIssue, ...]:
        return tuple(value)

    @field_serializer("renta_income_issues")
    def _serialize_renta_income_issues(
        self,
        value: Sequence[RentaIncomeLedgerAggregationIssue],
    ) -> tuple[RentaIncomeLedgerAggregationIssue, ...]:
        return tuple(value)


class LedgerIvaAggregationSourceResolver:
    """Source mesh resolver for repository-backed IVA ledger bindings."""

    resolver_id = "ledger_iva_aggregation"
    owned_sources = ("ledger_iva_aggregation",)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol | None = None) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_iva_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        try:
            aggregation = aggregate_iva_ledger_observations_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period_for_modelo(
                    filing_year=context.filing_year,
                    period=context.period.registry_token,
                ),
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
            binding_values=resolve_ledger_iva_aggregation_binding_values(
                context.revision,
                aggregation.observations,
            ),
            source_transaction_ids=tuple(sorted(transaction_ids)),
            diagnostics=tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="ledger_iva_aggregation",
                    resolver_id=self.resolver_id,
                    message=issue.detail,
                )
                for issue in aggregation.issues
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="source_issue",
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
    """Source mesh resolver for repository-backed Renta expense bindings."""

    resolver_id = "ledger_renta_expense_aggregation"
    owned_sources = ("ledger_renta_expense_aggregation",)

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
                    period=context.period.registry_token,
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
            ),
            provenance=tuple(
                provenance
                for observation in aggregation.observations
                for provenance in _renta_observation_provenance(observation)
            ),
        )


class LedgerRentaIncomeAggregationSourceResolver:
    """Source mesh resolver for repository-backed M130 actividad-económica income bindings."""

    resolver_id = "ledger_renta_income_aggregation"
    owned_sources = ("ledger_renta_income_aggregation",)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol | None = None) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_income_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            period=context.period.registry_token,
        )
        try:
            aggregation = aggregate_renta_income_ledger_from_repositories(
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
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_renta_income_aggregation_binding_values(
                context.revision,
                aggregation.observations,
            ),
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
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_renta_income_aggregation",
                    source_ref=f"transaction:{observation.transaction_id}",
                )
                for observation in aggregation.observations
            ),
        )


def aggregation_period_for_modelo(*, filing_year: int, period: str) -> Period:
    """Translate a canonical ``StandardPeriodCode`` token to a core period.

    Accepts only the span-shaped canonical AEAT tokens the calc engine and the
    CLI ledger filter share: quarters (``1T``-``4T``), the annual period
    (``0A``), and months (``01``-``12``). The result is the typed core
    :class:`Period` consumed by ledger filters. Any other token raises
    :class:`AggregationValidationError`.
    """
    normalized = period.strip().upper()
    try:
        resolved = Period.from_year_and_code(filing_year, normalized)
    except PeriodError as exc:
        raise AggregationValidationError(
            t("aggregation.modelo_bindings.errors.unsupported_period"),
            context={"filing_year": str(filing_year), "period": period},
        ) from exc
    if not resolved.has_date_span():
        raise AggregationValidationError(
            t("aggregation.modelo_bindings.errors.unsupported_period"),
            context={"filing_year": str(filing_year), "period": period},
        )
    return resolved


def _revision_has_binding_source(revision: ModeloRevision, source: str) -> bool:
    return any(binding.source == source for binding in revision.bindings)


def _empty_source_resolution(resolver_id: str, owned_sources: tuple[str, ...]) -> CalculationSourceResolution:
    return CalculationSourceResolution(resolver_id=resolver_id, owned_sources=owned_sources)


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
    "LedgerRentaIncomeAggregationSourceResolver",
    "ModeloLedgerBindingAggregation",
    "aggregation_period_for_modelo",
]
