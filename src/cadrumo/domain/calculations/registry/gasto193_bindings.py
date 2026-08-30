"""Modelo 193 gastos-relationship row-set binding helpers.

Modelo 193's hoja anexo (registro tipo 2, relación de gastos) carries one row
per contribuyente for whom the declarante perceived the art. 26.1.a) LIRPF
gastos de administracion y deposito de valores. This family resolves those
rows from per-contribuyente gasto observations and feeds the declarante's
IMPORTE DE GASTOS total (positions 220-234) through the ``gastos_sum`` fact.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ....core.models import STRICT_FROZEN_CONFIG
from ....core.aggregation import BindingAggregationOp
from ....core.identity import TaxIdIdentityToken
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import (
    BindingExportDataType,
)
from .binding_selector_utils import (
    selector_as_dict as _selector_as_dict,
)
from .errors import RegistryValidationError
from .schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "Gasto193Observation",
    "_Gasto193Selector",
    "resolve_gasto193_binding_row_values",
    "resolve_gasto193_binding_values",
    "validate_gasto193_binding_selector_shape",
]

_Gasto193RowField = Literal[
    "contributor_tax_id",
    "contributor_legal_name",
    "representative_tax_id",
    "importe_gastos",
]
_Gasto193Fact = Literal["row_field", "gastos_sum"]


class Gasto193Observation(BaseModel):
    """One modelo 193 gastos-relationship row: contribuyente plus annual gastos."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    contributor_tax_id: TaxIdIdentityToken = Field(min_length=1, max_length=64)
    contributor_legal_name: str = Field(default="", max_length=200)
    representative_tax_id: str | None = Field(default=None, min_length=9, max_length=9)
    """NIF of the minor's legal representative, declared by the design only when
    the contribuyente is a minor; spaces elsewhere."""
    transaction_date: date
    importe_gastos: Decimal = Decimal("0")
    """The annual gastos de administracion y deposito amount (positions 195-206),
    the design's own zeros when none."""

    def _non_negative_gastos(self) -> None:
        if self.importe_gastos < Decimal("0"):
            raise RegistryValidationError("gasto amounts must be non-negative")


class _Gasto193Selector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    fact: _Gasto193Fact
    claves: tuple[str, ...] = ()
    row_field: _Gasto193RowField | None = None
    grouping: Literal["per_gasto193_contribuyente"] | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: BindingExportDataType | None = None


def _gasto193_selector(binding: DataBindingDefinition) -> _Gasto193Selector:
    try:
        return _Gasto193Selector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed gasto193 selector") from exc


def validate_gasto193_binding_selector_shape(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``gasto193`` binding's selector shape and fact/aggregation invariants."""
    try:
        selector = _gasto193_selector(binding)
    except ValueError as exc:
        return [
            f"binding {binding.id!r} (source={binding.source!r}) selector violates {_Gasto193Selector.__name__}: {exc}",
        ]
    try:
        op = binding_aggregation_op(binding)
        if selector.fact == "row_field":
            if op != BindingAggregationOp.ROWS:
                raise RegistryValidationError("gasto193 fact 'row_field' requires aggregation op 'rows'")
            if selector.row_field is None:
                raise RegistryValidationError("gasto193 fact 'row_field' requires a 'row_field' selector key")
            if selector.grouping is None:
                raise RegistryValidationError("gasto193 fact 'row_field' requires a 'grouping' selector key")
        elif selector.fact == "gastos_sum":
            if op != BindingAggregationOp.SUM:
                raise RegistryValidationError("gasto193 fact 'gastos_sum' requires aggregation op 'sum'")
    except RegistryValidationError as exc:
        return [f"binding {binding.id!r} (source={binding.source!r}) gasto193 invariants violated: {exc}"]
    return []


def resolve_gasto193_binding_values(
    revision: ModeloRevision,
    observations: Iterable[Gasto193Observation],
) -> dict[str, Decimal]:
    """Resolve every ``gasto193`` scalar-sum binding on the revision to its aggregated value."""
    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if str(getattr(binding, "source", "")) != "gasto193":
            continue
        selector = _gasto193_selector(binding)
        if selector.fact == "row_field":
            continue
        resolved[str(binding.id)] = sum(
            (obs.importe_gastos for obs in available),
            Decimal("0"),
        )
    return resolved


def _build_gasto193_rows(
    observations: tuple[Gasto193Observation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    accum: dict[str, dict[str, Decimal | str]] = {}
    for observation in observations:
        identity: dict[str, Decimal | str] = {
            "contributor_tax_id": observation.contributor_tax_id,
            "contributor_legal_name": observation.contributor_legal_name,
            "importe_gastos": Decimal("0"),
        }
        if observation.representative_tax_id is not None:
            identity["representative_tax_id"] = observation.representative_tax_id
        bucket = accum.setdefault(observation.contributor_tax_id, identity)
        previous = bucket["importe_gastos"]
        assert isinstance(previous, Decimal)
        bucket["importe_gastos"] = previous + observation.importe_gastos
    return tuple(accum[key] for key in sorted(accum.keys()))


def resolve_gasto193_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[Gasto193Observation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve row-producer gasto193 bindings into per-row indexed values.

    ``representative_tax_id`` is emitted as the design's own spaces when no
    observation carries it (the field is declared only for minor contribuyentes).
    """
    available = tuple(observations)
    rows = _build_gasto193_rows(available)
    resolved: dict[tuple[str, int], Decimal | str] = {}
    for binding in revision.bindings:
        if str(getattr(binding, "source", "")) != "gasto193":
            continue
        selector = _gasto193_selector(binding)
        if selector.fact != "row_field":
            continue
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None and selector.row_field == "representative_tax_id":
                value = " " * 9
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced "
                    f"for gasto193 row {row_index}",
                )
            resolved[(str(binding.id), row_index)] = value
    return resolved
