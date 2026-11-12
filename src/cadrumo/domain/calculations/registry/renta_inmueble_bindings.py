"""The binding family that places one let property's figures on its own ``Inmueble`` row of Modelo 100.

The official design repeats ``Inmueble`` once per property held in the ejercicio,
and every casilla of the group occurs once per occurrence. A binding of this
family names the box its column fills and the column it reads; the revision's
own declarations say which box receives which column, so no box number lives in
code and each edition answers for itself.

The columns themselves -- what one property states -- belong to the source that
builds the occurrences. This module checks the shape of a declaration and lists
the columns a revision declares; the source refuses a column name it does not
know, so a selector the registry admits but no source can read is never filled
with a blank.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated, Final, Literal

from pydantic import AfterValidator, BaseModel, Field

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import provider_member
from .errors import RegistryValidationError
from .form_codes import form_role_validator
from .ledger_binding_validation import ledger_binding_build_diagnostics, ledger_binding_selector

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision

_ROW_FIELD_TOKEN: Final = re.compile(r"^[a-z][a-z0-9_]*$")


def _row_field_token(value: str) -> str:
    if not _ROW_FIELD_TOKEN.fullmatch(value):
        raise ValueError("a renta_inmueble row column is a lower-case token")
    return value


class RentaInmuebleProvider(BaseModel):
    """Validated form of a ``renta_inmueble`` binding selector: one column of a property's row."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.RENTA_INMUEBLE] = BindingSourceKind.RENTA_INMUEBLE
    modelo: Annotated[str, AfterValidator(form_role_validator("renta.annual"))]
    period: Literal["0A"] = "0A"
    fact: Literal["row_field"] = "row_field"
    record: Literal["inmueble"] = "inmueble"
    grouping: Literal["per_inmueble"] = "per_inmueble"
    row_field: Annotated[str, AfterValidator(_row_field_token)] = Field(min_length=1, max_length=64)
    """The column of the occurrence the binding reads, named by the source that builds it.

    A column of one numbered tenant names the tenant's slot in its own token.
    """
    target_casilla_id: CasillaId


def _validate_definition(binding: BindingDefinition) -> None:
    ledger_binding_selector(binding, BindingSourceKind.RENTA_INMUEBLE, RentaInmuebleProvider)
    if binding_aggregation_op(binding) is not BindingAggregationOp.ROWS:
        raise RegistryValidationError(f"binding {binding.id!r} requires aggregation op 'rows'")


def validate_renta_inmueble_binding(binding: BindingDefinition) -> list[str]:
    """Validate a ``renta_inmueble`` binding at registry-build time.

    Returns:
        The failures found, empty when the binding is valid.
    """
    return ledger_binding_build_diagnostics(binding, RentaInmuebleProvider, _validate_definition)


def renta_inmueble_columns(revision: ModeloRevision) -> tuple[tuple[BindingDefinition, RentaInmuebleProvider], ...]:
    """Return every ``renta_inmueble`` column this :class:`ModeloRevision` declares, in declaration order."""
    return tuple(
        (binding, provider_member(binding, RentaInmuebleProvider))
        for binding in revision.bindings
        if binding.source == BindingSourceKind.RENTA_INMUEBLE
    )


__all__ = [
    "RentaInmuebleProvider",
    "renta_inmueble_columns",
    "validate_renta_inmueble_binding",
]
