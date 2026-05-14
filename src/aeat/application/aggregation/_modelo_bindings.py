"""Modelo binding values derived from bucket-local ledger catalogues."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from ...domain.calculations.registry import (
    ModeloRevision,
    resolve_ledger_iva_aggregation_binding_values,
    resolve_ledger_renta_expense_aggregation_binding_values,
)
from ...domain.invoices import InvoiceCatalogueRepository
from ...domain.transactions import TransactionCatalogueRepository
from ._errors import AggregationValidationError, t
from ._iva_ledger import (
    IvaLedgerAggregationIssue,
    aggregate_iva_ledger_observations_from_repositories,
)
from ._renta_ledger import (
    RentaLedgerAggregationIssue,
    aggregate_renta_ledger_expenses_from_repositories,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


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

    @field_serializer("renta_issues")
    def _serialize_renta_issues(
        self,
        value: Sequence[RentaLedgerAggregationIssue],
    ) -> tuple[RentaLedgerAggregationIssue, ...]:
        return tuple(value)


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
    aggregation_period = aggregation_period_for_modelo(filing_year=filing_year, period=period)

    if _revision_has_binding_source(revision, "ledger_iva_aggregation"):
        iva_aggregation = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=bucket_id,
            period=aggregation_period,
            transaction_repository=transaction_repository,
        )
        binding_values.update(
            resolve_ledger_iva_aggregation_binding_values(revision, iva_aggregation.observations)
        )
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

    return ModeloLedgerBindingAggregation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        binding_values=binding_values,
        source_transaction_ids=tuple(sorted(source_transaction_ids)),
        iva_issues=iva_issues,
        renta_issues=renta_issues,
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


__all__ = [
    "ModeloLedgerBindingAggregation",
    "aggregation_period_for_modelo",
    "resolve_modelo_ledger_binding_values_from_repositories",
]
