"""Projection from canonical M303 prorrata rows to official endpoints.

The five ``DP30305`` activity rows are durable children of the encrypted
``ProrrataRegister``. This registry-side module reads the revision's reviewed
endpoint declarations and projects those row facts into their five fixed
official slots. It neither introduces an independent scalar input channel nor
renders a withdrawn export layout.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from ....core import M303ProrrataActivityProjectionField, M303ProrrataActivityProjectionRef
from ....core.models import STRICT_FROZEN_CONFIG
from ...prorrata_register import ProrrataActivityRow, ProrrataRegister
from .errors import RegistryValidationError

_FIELDS = frozenset(M303ProrrataActivityProjectionField)


class M303ProrrataActivityEndpointValue(BaseModel):
    """One official endpoint paired with the value projected from its row child."""

    model_config = STRICT_FROZEN_CONFIG

    projection_ref: M303ProrrataActivityProjectionRef
    value: str | Decimal


class M303ProrrataActivityRowProjection(BaseModel):
    """The five reviewed official endpoint values for one persisted row slot."""

    model_config = STRICT_FROZEN_CONFIG

    slot: int = Field(ge=1, le=5)
    endpoints: tuple[M303ProrrataActivityEndpointValue, ...] = Field(min_length=5, max_length=5)

    def endpoint_values(self) -> tuple[M303ProrrataActivityEndpointValue, ...]:
        """Return the row's endpoint values in the official field order."""
        return self.endpoints


def project_m303_prorrata_activity_rows(
    *,
    projection_refs: tuple[M303ProrrataActivityProjectionRef, ...],
    register: ProrrataRegister,
    ejercicio: int,
) -> tuple[M303ProrrataActivityRowProjection, ...]:
    """Project an applicable register's five row children into a revision's endpoints.

    The registry determines which official box belongs to which fixed row slot;
    the register determines the values. An inactive prorrata year has no row
    projection. An active year whose canonical collection is incomplete fails
    rather than yielding blank or zero endpoint values.
    """
    if not register.requires_activity_rows_for(ejercicio):
        if projection_refs:
            _validate_projection_refs(projection_refs)
        return ()
    if not register.activity_rows_complete_for(ejercicio):
        raise RegistryValidationError.for_prorrata_activity_rows_incomplete(ejercicio=ejercicio)
    refs = _validate_projection_refs(projection_refs)
    return tuple(_project_row(row, refs=refs[row.slot]) for row in register.activity_rows_for_ejercicio(ejercicio))


def _validate_projection_refs(
    refs: tuple[M303ProrrataActivityProjectionRef, ...],
) -> dict[int, dict[M303ProrrataActivityProjectionField, M303ProrrataActivityProjectionRef]]:
    resolved: dict[int, dict[M303ProrrataActivityProjectionField, M303ProrrataActivityProjectionRef]] = {}
    casilla_ids = tuple(ref.casilla_id for ref in refs)
    if len(set(casilla_ids)) != len(casilla_ids):
        raise RegistryValidationError("m303 prorrata projection references duplicate endpoint casillas")
    for ref in refs:
        by_field = resolved.setdefault(ref.slot, {})
        if ref.field in by_field:
            raise RegistryValidationError(
                f"m303 prorrata projection has duplicate reference for slot {ref.slot} field {ref.field.value!r}",
            )
        by_field[ref.field] = ref
    expected = {slot: set(_FIELDS) for slot in range(1, 6)}
    actual = {slot: set(by_field) for slot, by_field in resolved.items()}
    if actual != expected:
        raise RegistryValidationError(
            "m303 prorrata projection endpoint matrix is incomplete or malformed: "
            f"expected {expected!r}, got {actual!r}",
        )
    return resolved


def _project_row(
    row: ProrrataActivityRow,
    *,
    refs: dict[M303ProrrataActivityProjectionField, M303ProrrataActivityProjectionRef],
) -> M303ProrrataActivityRowProjection:
    """Pair one canonical row's typed values with its revision-selected endpoints."""
    values: dict[M303ProrrataActivityProjectionField, str | Decimal] = {
        M303ProrrataActivityProjectionField.CNAE: row.cnae_code,
        M303ProrrataActivityProjectionField.OPERACIONES_TOTAL: row.operaciones_total,
        M303ProrrataActivityProjectionField.OPERACIONES_CON_DERECHO: row.operaciones_con_derecho,
        M303ProrrataActivityProjectionField.TIPO: row.prorrata_type.value,
        M303ProrrataActivityProjectionField.PORCENTAJE: row.percentage,
    }
    return M303ProrrataActivityRowProjection(
        slot=row.slot,
        endpoints=tuple(
            M303ProrrataActivityEndpointValue(projection_ref=refs[field], value=values[field])
            for field in M303ProrrataActivityProjectionField
        ),
    )


__all__ = [
    "M303ProrrataActivityEndpointValue",
    "M303ProrrataActivityRowProjection",
    "project_m303_prorrata_activity_rows",
]
