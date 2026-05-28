"""Modelo binding values derived from bucket-local ledger catalogues."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...domain.calculations.registry import (
    ModeloRevision,
    resolve_ledger_iva_aggregation_binding_values,
    resolve_ledger_renta_expense_aggregation_binding_values,
    resolve_ledger_renta_income_aggregation_binding_values,
)
from ...domain.invoices import InvoiceCatalogueRepository
from ...domain.renta import RentaDeductibleExpenseObservation
from ...domain.transactions import TransactionCatalogueRepository
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

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)


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

    def __init__(self, *, transaction_repository: TransactionCatalogueRepository | None = None) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_iva_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        try:
            aggregation = aggregate_iva_ledger_observations_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period_for_modelo(filing_year=context.filing_year, period=context.period),
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
        transaction_repository: TransactionCatalogueRepository | None = None,
        invoice_repository: InvoiceCatalogueRepository | None = None,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._invoice_repository = invoice_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_expense_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        try:
            aggregation = aggregate_renta_ledger_expenses_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period_for_modelo(filing_year=context.filing_year, period=context.period),
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
                sorted(observation.transaction_id for observation in aggregation.observations)
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

    def __init__(self, *, transaction_repository: TransactionCatalogueRepository | None = None) -> None:
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if not _revision_has_binding_source(context.revision, "ledger_renta_income_aggregation"):
            return _empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(filing_year=context.filing_year, period=context.period)
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
                sorted(observation.transaction_id for observation in aggregation.observations)
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


def resolve_modelo_ledger_binding_values_from_repositories(
    *,
    bucket_id: str,
    modelo: str,
    revision: ModeloRevision,
    filing_year: int,
    period: str,
    transaction_repository: TransactionCatalogueRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
) -> ModeloLedgerBindingAggregation:
    """Resolve ledger-backed registry bindings from the active bucket."""

    binding_values: dict[str, Decimal] = {}
    source_transaction_ids: set[str] = set()
    iva_issues: tuple[IvaLedgerAggregationIssue, ...] = ()
    renta_issues: tuple[RentaLedgerAggregationIssue, ...] = ()
    renta_income_issues: tuple[RentaIncomeLedgerAggregationIssue, ...] = ()
    aggregation_period = aggregation_period_for_modelo(filing_year=filing_year, period=period)

    if _revision_has_binding_source(revision, "ledger_iva_aggregation"):
        iva_aggregation = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=bucket_id,
            period=aggregation_period,
            transaction_repository=transaction_repository,
        )
        binding_values.update(resolve_ledger_iva_aggregation_binding_values(revision, iva_aggregation.observations))
        source_transaction_ids.update(observation.ledger_id for observation in iva_aggregation.observations)
        source_transaction_ids.update(reference.transaction_id for reference in iva_aggregation.prorrata_references)
        iva_issues = tuple(iva_aggregation.issues)

    if _revision_has_binding_source(revision, "ledger_renta_expense_aggregation"):
        renta_aggregation = aggregate_renta_ledger_expenses_from_repositories(
            bucket_id=bucket_id,
            period=aggregation_period,
            transaction_repository=transaction_repository,
            invoice_repository=invoice_repository,
            profile_year=filing_year,
        )
        binding_values.update(
            resolve_ledger_renta_expense_aggregation_binding_values(
                revision,
                renta_aggregation.observations,
            )
        )
        source_transaction_ids.update(observation.transaction_id for observation in renta_aggregation.observations)
        renta_issues = tuple(renta_aggregation.issues)

    if _revision_has_binding_source(revision, "ledger_renta_income_aggregation"):
        renta_income_aggregation = aggregate_renta_income_ledger_from_repositories(
            bucket_id=bucket_id,
            period=aggregation_period,
            transaction_repository=transaction_repository,
        )
        binding_values.update(
            resolve_ledger_renta_income_aggregation_binding_values(
                revision,
                renta_income_aggregation.observations,
            )
        )
        source_transaction_ids.update(
            observation.transaction_id for observation in renta_income_aggregation.observations
        )
        renta_income_issues = tuple(renta_income_aggregation.issues)

    return ModeloLedgerBindingAggregation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        binding_values=binding_values,
        source_transaction_ids=tuple(sorted(source_transaction_ids)),
        iva_issues=iva_issues,
        renta_issues=renta_issues,
        renta_income_issues=renta_income_issues,
    )


def aggregation_period_for_modelo(*, filing_year: int, period: str) -> str:
    """Translate registry/modelo period tokens to aggregation period tokens."""

    normalized = period.strip().upper()
    quarter_map = {"1T": "Q1", "2T": "Q2", "3T": "Q3", "4T": "Q4"}
    if normalized in quarter_map:
        return f"{filing_year}{quarter_map[normalized]}"
    if normalized in {"Q1", "Q2", "Q3", "Q4"}:
        return f"{filing_year}{normalized}"
    if normalized in {"0A", "A", "ANUAL", "ANNUAL"}:
        return str(filing_year)
    if normalized.startswith("M") and len(normalized) == 3 and normalized[1:].isdigit():
        return f"{filing_year}-{normalized[1:]}"
    if len(normalized) == 2 and normalized.isdigit():
        return f"{filing_year}-{normalized}"
    raise AggregationValidationError(
        t("aggregation.modelo_bindings.errors.unsupported_period"),
        context={"filing_year": str(filing_year), "period": period},
    )


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
        )
    ]
    if observation.invoice_id is not None:
        provenance.append(
            CalculationSourceProvenance(
                source_kind="ledger_renta_expense_aggregation",
                source_ref=f"purchase-invoice-evidence:{observation.invoice_id}",
            )
        )
    return tuple(provenance)


__all__ = [
    "LedgerIvaAggregationSourceResolver",
    "LedgerRentaExpenseAggregationSourceResolver",
    "LedgerRentaIncomeAggregationSourceResolver",
    "ModeloLedgerBindingAggregation",
    "aggregation_period_for_modelo",
    "resolve_modelo_ledger_binding_values_from_repositories",
]
