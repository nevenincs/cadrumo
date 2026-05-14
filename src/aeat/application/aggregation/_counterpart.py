"""347/349 counterpart aggregator (informational declarations).

Modelo 347: Operaciones con terceros — annual declaration of operations
with the same counterparty whose total in the year exceeds €3,005.06.
Modelo 349: Operaciones intracomunitarias — quarterly + annual EU
member-state operations (delivery, acquisition, services).

Both modelos aggregate per (counterparty_nif, operation_kind) and apply
a declaration threshold downstream. The aggregator here produces the
raw per-counterparty rollups; the threshold gate (€3005.06 for 347)
lives in the modelo binding consumer.

Per apex §12 R21 and the per-modelo-aggregation-pipeline ADR. Bare
``invoice`` source-kind is rejected at observation construction; the
four canonical source kinds are accepted.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OperationKind347(StrEnum):
    """Modelo 347 operation kinds (clave de operación).

    Source: AEAT Modelo 347 instrucciones.
    """

    DELIVERY = "entregas_y_prestaciones"          # clave A
    ACQUISITION = "adquisiciones_y_recepciones"   # clave B
    INSURANCE = "operaciones_seguros"             # clave C
    RENTAL = "arrendamientos_locales"             # clave D
    SUBSIDY = "subvenciones_y_ayudas"             # clave E


class OperationKind349(StrEnum):
    """Modelo 349 intracomunitarias operation kinds.

    Source: AEAT Modelo 349 instrucciones. The clave maps from the
    underlying directionality (entrega/adquisición) and operation
    type (bienes/servicios).
    """

    INTRA_DELIVERY = "entrega_intracomunitaria_bienes"        # clave E
    INTRA_ACQUISITION = "adquisicion_intracomunitaria_bienes" # clave A
    INTRA_SERVICE_OUT = "prestacion_servicios_intracom"        # clave S
    INTRA_SERVICE_IN = "adquisicion_servicios_intracom"        # clave I
    TRIANGULAR = "triangular"                                   # clave T


class CounterpartObservation(BaseModel):
    """One typed observation for a 347 or 349 aggregator pass."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_kind: str = Field(min_length=1)
    source_object_id: str = Field(min_length=1)
    counterparty_nif: str = Field(min_length=1, max_length=20)
    counterparty_name: str = Field(default="", max_length=200)
    counterparty_country: str = Field(default="ES", min_length=2, max_length=2)
    operation_kind: str = Field(min_length=1)
    operation_period: str = Field(min_length=1)  # ISO quarter / year identifier
    taxable_base: Decimal = Field(ge=Decimal("0"))
    invoice_total: Decimal = Field(ge=Decimal("0"))
    accrued_on: str = Field(min_length=10, max_length=10)

    @field_validator("source_kind")
    @classmethod
    def _reject_bare_invoice_source(cls, value: str) -> str:
        if value == "invoice":
            raise ValueError(
                "bare 'invoice' source-kind is forbidden; use ledger_transaction, "
                "purchase_invoice_evidence, payable_invoice, or collectible_invoice",
            )
        return value

    @field_validator("counterparty_country")
    @classmethod
    def _country_is_uppercase(cls, value: str) -> str:
        if value != value.upper():
            raise ValueError(f"counterparty_country must be uppercase ISO-3166 alpha-2, got {value!r}")
        return value


class CounterpartRollup(BaseModel):
    """One (counterparty_nif, operation_kind) rollup row."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    counterparty_nif: str = Field(min_length=1, max_length=20)
    counterparty_name: str = Field(default="", max_length=200)
    counterparty_country: str = Field(min_length=2, max_length=2)
    operation_kind: str = Field(min_length=1)
    observations_count: int = Field(ge=0)
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_invoice_total: Decimal = Field(ge=Decimal("0"))


class CounterpartAggregation(BaseModel):
    """347 / 349 counterpart aggregation output."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str = Field(min_length=1)
    period: str = Field(min_length=1)
    rollups: tuple[CounterpartRollup, ...] = Field(default_factory=tuple)
    total_counterparties: int = Field(ge=0)
    total_taxable_base: Decimal = Field(ge=Decimal("0"))
    total_invoice_total: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def _totals_match_rollups(self) -> "CounterpartAggregation":
        computed_base = sum((row.total_taxable_base for row in self.rollups), Decimal("0"))
        computed_total = sum((row.total_invoice_total for row in self.rollups), Decimal("0"))
        if computed_base != self.total_taxable_base:
            raise ValueError(
                f"total_taxable_base {self.total_taxable_base} != sum of rollups {computed_base}",
            )
        if computed_total != self.total_invoice_total:
            raise ValueError(
                f"total_invoice_total {self.total_invoice_total} != sum of rollups {computed_total}",
            )
        unique_counterparties = {row.counterparty_nif for row in self.rollups}
        if len(unique_counterparties) != self.total_counterparties:
            raise ValueError(
                f"total_counterparties {self.total_counterparties} != distinct NIFs "
                f"{len(unique_counterparties)}",
            )
        return self


_MODELO_347_KINDS: frozenset[str] = frozenset(k.value for k in OperationKind347)
_MODELO_349_KINDS: frozenset[str] = frozenset(k.value for k in OperationKind349)
_MODELO_KIND_CATALOGUE: dict[str, frozenset[str]] = {
    "347": _MODELO_347_KINDS,
    "349": _MODELO_349_KINDS,
}


def _filter_observations_for_modelo(
    observations: tuple[CounterpartObservation, ...],
    modelo: str,
) -> tuple[CounterpartObservation, ...]:
    if modelo not in _MODELO_KIND_CATALOGUE:
        msg = f"counterpart aggregator for modelo {modelo!r} is not implemented"
        raise NotImplementedError(msg)
    eligible = _MODELO_KIND_CATALOGUE[modelo]
    return tuple(o for o in observations if o.operation_kind in eligible)


def _aggregate_for_modelo(
    observations: tuple[CounterpartObservation, ...],
    *,
    modelo: str,
    period: str,
) -> CounterpartAggregation:
    filtered = _filter_observations_for_modelo(observations, modelo=modelo)
    grouped: dict[tuple[str, str], list[CounterpartObservation]] = {}
    names: dict[str, str] = {}
    countries: dict[str, str] = {}
    for obs in filtered:
        key = (obs.counterparty_nif, obs.operation_kind)
        grouped.setdefault(key, []).append(obs)
        if obs.counterparty_name and not names.get(obs.counterparty_nif):
            names[obs.counterparty_nif] = obs.counterparty_name
        countries[obs.counterparty_nif] = obs.counterparty_country
    rollups: list[CounterpartRollup] = []
    for (nif, op_kind), group in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        total_base = sum((g.taxable_base for g in group), Decimal("0"))
        total_invoice = sum((g.invoice_total for g in group), Decimal("0"))
        rollups.append(
            CounterpartRollup(
                counterparty_nif=nif,
                counterparty_name=names.get(nif, ""),
                counterparty_country=countries.get(nif, "ES"),
                operation_kind=op_kind,
                observations_count=len(group),
                total_taxable_base=total_base,
                total_invoice_total=total_invoice,
            ),
        )
    counterparties = {row.counterparty_nif for row in rollups}
    return CounterpartAggregation(
        modelo=modelo,
        period=period,
        rollups=tuple(rollups),
        total_counterparties=len(counterparties),
        total_taxable_base=sum((row.total_taxable_base for row in rollups), Decimal("0")),
        total_invoice_total=sum((row.total_invoice_total for row in rollups), Decimal("0")),
    )


def aggregate_counterpart_347(
    observations: tuple[CounterpartObservation, ...],
    *,
    period: str,
) -> CounterpartAggregation:
    """Aggregate Modelo 347 (operaciones con terceros, annual).

    Filters to 347 operation kinds. Threshold gating (the €3,005.06
    declaration floor) belongs to the modelo binding consumer; this
    aggregator returns raw per-counterparty totals.
    """
    return _aggregate_for_modelo(observations, modelo="347", period=period)


def aggregate_counterpart_349(
    observations: tuple[CounterpartObservation, ...],
    *,
    period: str,
) -> CounterpartAggregation:
    """Aggregate Modelo 349 (operaciones intracomunitarias).

    Filters to 349 intracomunitarias operation kinds. The modelo
    binding consumer applies the additional NIF-IVA / GROI readiness
    gates per apex §5.4.
    """
    return _aggregate_for_modelo(observations, modelo="349", period=period)


THRESHOLD_347_EUR: Decimal = Decimal("3005.06")
"""Modelo 347 declaration floor: counterparties whose annual operations
total to at most this amount are NOT declarable per AEAT instrucciones."""


def declarable_for_347(rollup: CounterpartRollup) -> bool:
    """Return True iff a counterparty rollup exceeds the 347 declaration floor."""
    return rollup.total_invoice_total > THRESHOLD_347_EUR


__all__ = [
    "CounterpartAggregation",
    "CounterpartObservation",
    "CounterpartRollup",
    "OperationKind347",
    "OperationKind349",
    "THRESHOLD_347_EUR",
    "aggregate_counterpart_347",
    "aggregate_counterpart_349",
    "declarable_for_347",
]
