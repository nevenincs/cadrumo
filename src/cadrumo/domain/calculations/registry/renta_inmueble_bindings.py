"""The binding family that places one let property's figures on its own ``Inmueble`` row of Modelo 100.

The official design repeats ``Inmueble`` once per property held in the ejercicio,
and every casilla of the group occurs once per occurrence. A binding of this
family names the box its column fills and the column it reads; the revision's
own declarations say which box receives which column, so no box number lives in
code and each edition answers for itself.

A total binding sums one column over every occurrence, for a box of the
results that the rows account for; it names the column's own box.

The columns themselves -- what one property states -- belong to the source that
builds the occurrences. This module checks the shape of a declaration and lists
the columns a revision declares; the source refuses a column name it does not
know, so a selector the registry admits but no source can read is never filled
with a blank.

Anexo C.1 follows each property's interest and repair excess by the ejercicio it
arose in (LIRPF art. 23.1.a.1.º; RIRPF art. 13.a): what was pending at the start
of the period, what this return applies and what still carries on. A column of
it names its origin as data, ``origin = { back = n, part = "opening" }``: the
origin is the ejercicio ``n`` years before the one filed. The registry's carry
window parameter says how many years an excess carries, so the origin columns
cover every year of that window and the oldest has no box for what carries on.
No origin year is computed in code: a column is chosen by its declared origin.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Final, Literal, Self

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, model_validator

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_absence_attestation import AbsenceAttestationFamily
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import provider_member
from .binding_temporal import RelativeToFilingYear
from .errors import RegistryValidationError
from .form_codes import form_role_validator
from .ledger_binding_validation import ledger_binding_build_diagnostics, ledger_binding_selector
from .schema_base import coerce_enum_member

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision

_ROW_FIELD_TOKEN: Final = re.compile(r"^[a-z][a-z0-9_]*$")

ORIGIN_ROW_FIELD: Final = "gastos_pendientes_origen"
"""The one column token of anexo C.1's per-origin amounts; each binding of it names its origin."""

CARRY_YEARS_PARAMETER: Final = "renta-rental-gastos-pendientes-carry-years"
"""The registry parameter stating how many following ejercicios an excess carries into."""


def _row_field_token(value: str) -> str:
    if not _ROW_FIELD_TOKEN.fullmatch(value):
        raise ValueError("a renta_inmueble row column is a lower-case token")
    return value


class RentaInmuebleOriginPart(StrEnum):
    """Which amount of one origin year an anexo C.1 column states."""

    OPENING = "opening"
    """Pending at the start of the period: a carry of earlier returns, never computed."""
    APPLIED = "applied"
    """Applied in this return."""
    CARRIED = "carried"
    """Still pending for the following ejercicios."""


class RentaInmuebleOrigin(BaseModel):
    """The origin year an anexo C.1 column speaks of, counted back from the ejercicio filed, and its amount."""

    model_config = STRICT_FROZEN_CONFIG

    back: Annotated[int, RelativeToFilingYear()] = Field(ge=1)
    """How many ejercicios before the one filed the excess arose."""
    part: Annotated[RentaInmuebleOriginPart, BeforeValidator(coerce_enum_member(RentaInmuebleOriginPart))]


class RentaInmuebleProvider(BaseModel):
    """Validated form of a ``renta_inmueble`` binding selector: one column of a property's row, or its total."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.RENTA_INMUEBLE] = BindingSourceKind.RENTA_INMUEBLE
    modelo: Annotated[str, AfterValidator(form_role_validator("renta.annual"))]
    period: Literal["0A"] = "0A"
    fact: Literal["row_field", "total"] = "row_field"
    """``row_field`` places the column on every row; ``total`` sums it over every row."""
    record: Literal["inmueble"] = "inmueble"
    grouping: Literal["per_inmueble"] = "per_inmueble"
    row_field: Annotated[str, AfterValidator(_row_field_token)] = Field(min_length=1, max_length=64)
    """The column of the occurrence the binding reads, named by the source that builds it.

    A column of one numbered tenant names the tenant's slot in its own token.
    """
    target_casilla_id: CasillaId
    origin: RentaInmuebleOrigin | None = None
    """The origin year and amount of an anexo C.1 column; declared on that column only."""

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _origin_only_on_the_origin_column(self) -> Self:
        if (self.origin is not None) != (self.row_field == ORIGIN_ROW_FIELD):
            raise RegistryValidationError(
                f"a renta_inmueble column declares an origin exactly when its row field is {ORIGIN_ROW_FIELD!r}"
            )
        if self.origin is not None and self.fact != "row_field":
            raise RegistryValidationError("an anexo C.1 origin column is a row column, never a total")
        return self


def _validate_definition(binding: BindingDefinition) -> None:
    selector = ledger_binding_selector(binding, BindingSourceKind.RENTA_INMUEBLE, RentaInmuebleProvider)
    expected = BindingAggregationOp.SUM if selector.fact == "total" else BindingAggregationOp.ROWS
    if binding_aggregation_op(binding) is not expected:
        raise RegistryValidationError(f"binding {binding.id!r} requires aggregation op {expected.value!r}")


def validate_renta_inmueble_binding(binding: BindingDefinition) -> list[str]:
    """Validate a ``renta_inmueble`` binding at registry-build time.

    Returns:
        The failures found, empty when the binding is valid.
    """
    return ledger_binding_build_diagnostics(binding, RentaInmuebleProvider, _validate_definition)


def _declared(revision: ModeloRevision) -> tuple[tuple[BindingDefinition, RentaInmuebleProvider], ...]:
    return tuple(
        (binding, provider_member(binding, RentaInmuebleProvider))
        for binding in revision.bindings
        if binding.source == BindingSourceKind.RENTA_INMUEBLE
    )


def renta_inmueble_columns(revision: ModeloRevision) -> tuple[tuple[BindingDefinition, RentaInmuebleProvider], ...]:
    """Return every ``renta_inmueble`` row column this :class:`ModeloRevision` declares, in declaration order."""
    return tuple(item for item in _declared(revision) if item[1].fact == "row_field")


def renta_inmueble_totals(revision: ModeloRevision) -> tuple[tuple[BindingDefinition, RentaInmuebleProvider], ...]:
    """Return every ``renta_inmueble`` column total this :class:`ModeloRevision` declares, in declaration order."""
    return tuple(item for item in _declared(revision) if item[1].fact == "total")


def renta_inmueble_origin_columns(
    revision: ModeloRevision,
) -> dict[RentaInmuebleOriginPart, dict[int, BindingDefinition]]:
    """Return the anexo C.1 origin columns ``revision`` declares, by part and by origin back.

    A pair declared twice keeps the first; :func:`renta_inmueble_origin_failures` refuses it.
    """
    columns: dict[RentaInmuebleOriginPart, dict[int, BindingDefinition]] = {}
    for binding, provider in renta_inmueble_columns(revision):
        if provider.origin is not None:
            columns.setdefault(provider.origin.part, {}).setdefault(provider.origin.back, binding)
    return columns


def _carry_windows(revision: ModeloRevision) -> tuple[Decimal, ...] | None:
    parameter = next((item for item in revision.parameters if item.id == CARRY_YEARS_PARAMETER), None)
    return None if parameter is None else tuple(value.value for value in parameter.values)


def carry_window_failures(windows: Iterable[Decimal]) -> tuple[str, ...]:
    """Say why a declared carry window is not a whole number of years of at least one."""
    return tuple(
        f"the carry window {window} of {CARRY_YEARS_PARAMETER} is not a whole number of years of at least one"
        for window in windows
        if window != window.to_integral_value() or window < 1
    )


def _origin_shape_failures(revision: ModeloRevision, window: int) -> list[str]:
    columns = renta_inmueble_origin_columns(revision)
    failures: list[str] = []
    expected = {
        RentaInmuebleOriginPart.OPENING: frozenset(range(1, window + 1)),
        RentaInmuebleOriginPart.APPLIED: frozenset(range(1, window + 1)),
        RentaInmuebleOriginPart.CARRIED: frozenset(range(1, window)),
    }
    for part, backs in expected.items():
        declared = frozenset(columns.get(part, {}))
        if declared != backs:
            failures.append(
                f"the anexo C.1 {part.value} columns cover origins {sorted(declared)}, and a carry window of "
                f"{window} years needs exactly {sorted(backs)}"
            )
    return failures


def _origin_declaration_failures(origins: Iterable[tuple[BindingDefinition, RentaInmuebleOrigin]]) -> list[str]:
    """Say which origin and part is declared twice, and which column takes the wrong statement."""
    failures: list[str] = []
    seen: dict[tuple[int, RentaInmuebleOriginPart], str] = {}
    for binding, origin in origins:
        key = (origin.back, origin.part)
        if key in seen:
            failures.append(
                f"bindings {seen[key]!r} and {binding.id!r} both declare origin back {origin.back} {origin.part.value}"
            )
        seen.setdefault(key, binding.id)
        stated = binding.absence_attestation is AbsenceAttestationFamily.RENTA_CAPITAL_INMOBILIARIO_GASTOS_PENDIENTES
        if stated != (origin.part is RentaInmuebleOriginPart.OPENING):
            failures.append(
                f"binding {binding.id!r}: an anexo C.1 opening column, and only it, takes the "
                f"{AbsenceAttestationFamily.RENTA_CAPITAL_INMOBILIARIO_GASTOS_PENDIENTES.value!r} statement"
            )
    return failures


def renta_inmueble_origin_failures(revision: ModeloRevision) -> tuple[str, ...]:
    """Validate the anexo C.1 origin columns of ``revision`` against its carry window.

    Each origin and part is declared once; the origins cover every year of the
    carry window, the oldest without a column for what carries on, since it
    carries nothing further; and the opening columns, which are carries of
    earlier returns, take the per-row statement of the pending-expense family
    while the computed ones take none.

    Returns:
        The failures found, empty when the revision declares no origin column or declares them well.
    """
    declared = [(binding, provider.origin) for binding, provider in renta_inmueble_columns(revision)]
    origins = [(binding, origin) for binding, origin in declared if origin is not None]
    if not origins:
        return ()
    failures = _origin_declaration_failures(origins)
    windows = _carry_windows(revision)
    if windows is None or len(windows) == 0:
        failures.append(f"anexo C.1 origin columns are declared but {CARRY_YEARS_PARAMETER} states no carry window")
        return tuple(failures)
    shape = carry_window_failures(windows)
    if shape:
        return (*failures, *shape)
    for window in sorted(set(windows)):
        failures.extend(_origin_shape_failures(revision, int(window)))
    return tuple(failures)


__all__ = [
    "CARRY_YEARS_PARAMETER",
    "ORIGIN_ROW_FIELD",
    "RentaInmuebleOrigin",
    "RentaInmuebleOriginPart",
    "RentaInmuebleProvider",
    "carry_window_failures",
    "renta_inmueble_columns",
    "renta_inmueble_origin_columns",
    "renta_inmueble_origin_failures",
    "renta_inmueble_totals",
    "validate_renta_inmueble_binding",
]
