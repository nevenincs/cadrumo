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

from ....core import STRICT_FROZEN_CONFIG, CasillaId
from ...prorrata_register import ProrrataActivityRow, ProrrataRegister
from ._errors import RegistryValidationError
from ._schema import CasillaDefinition, ModeloRevision
from ._schema_input_kind import InputKind

_FIELDS: tuple[str, ...] = (
    "cnae",
    "operaciones-total",
    "operaciones-con-derecho",
    "tipo",
    "porcentaje",
)
_ACTIVITY_SECTION_PREFIX = ("iva", "prorrata", "actividad")


class M303ProrrataActivityEndpointValue(BaseModel):
    """One official endpoint paired with the value projected from its row child."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    value: str | Decimal


class M303ProrrataActivityRowProjection(BaseModel):
    """The five reviewed official endpoint values for one persisted row slot."""

    model_config = STRICT_FROZEN_CONFIG

    slot: int = Field(ge=1, le=5)
    cnae: M303ProrrataActivityEndpointValue
    operaciones_total: M303ProrrataActivityEndpointValue
    operaciones_con_derecho: M303ProrrataActivityEndpointValue
    tipo: M303ProrrataActivityEndpointValue
    porcentaje: M303ProrrataActivityEndpointValue

    def endpoint_values(self) -> tuple[M303ProrrataActivityEndpointValue, ...]:
        """Return the row's endpoint values in the official field order."""
        return (
            self.cnae,
            self.operaciones_total,
            self.operaciones_con_derecho,
            self.tipo,
            self.porcentaje,
        )


def project_m303_prorrata_activity_rows(
    revision: ModeloRevision,
    *,
    register: ProrrataRegister,
    ejercicio: int,
) -> tuple[M303ProrrataActivityRowProjection, ...]:
    """Project an applicable register's five row children into a revision's endpoints.

    The registry determines which official box belongs to which fixed row slot;
    the register determines the values. An inactive prorrata year has no row
    projection. An active year whose canonical collection is incomplete fails
    rather than yielding blank or zero endpoint values.
    """
    endpoint_by_slot_and_field = _endpoint_by_slot_and_field(revision)
    if not register.requires_activity_rows_for(ejercicio):
        return ()
    if not register.activity_rows_complete_for(ejercicio):
        raise RegistryValidationError(
            f"modelo 303 per-activity prorrata rows are incomplete for ejercicio {ejercicio}",
        )
    return tuple(
        _project_row(row, endpoint_by_field=endpoint_by_slot_and_field[row.slot])
        for row in register.activity_rows_for_ejercicio(ejercicio)
    )


def _endpoint_by_slot_and_field(revision: ModeloRevision) -> dict[int, dict[str, CasillaDefinition]]:
    """Resolve and validate the revision's complete five-row endpoint matrix."""
    resolved: dict[int, dict[str, CasillaDefinition]] = {}
    for casilla in revision.casillas:
        section = tuple(casilla.section)
        if section[:3] != _ACTIVITY_SECTION_PREFIX:
            continue
        if len(section) != 5 or not section[3].startswith("fila_"):
            raise RegistryValidationError(
                f"m303 prorrata projection endpoint {casilla.id!r} has invalid section {section!r}",
            )
        try:
            slot = int(section[3].removeprefix("fila_"))
        except ValueError as exc:
            raise RegistryValidationError(
                f"m303 prorrata projection endpoint {casilla.id!r} has invalid row slot {section[3]!r}",
            ) from exc
        field = section[4]
        if slot not in range(1, 6) or field not in _FIELDS:
            raise RegistryValidationError(
                f"m303 prorrata projection endpoint {casilla.id!r} has unsupported slot/field {slot!r}/{field!r}",
            )
        if casilla.input_kind is not InputKind.PROJECTION_ONLY:
            raise RegistryValidationError(
                f"m303 prorrata projection endpoint {casilla.id!r} must be input_kind='projection_only'",
            )
        if casilla.formula is not None or casilla.binding is not None or casilla.alternate_bindings:
            raise RegistryValidationError(
                f"m303 prorrata projection endpoint {casilla.id!r} must not have an independent producer",
            )
        existing = resolved.setdefault(slot, {}).setdefault(field, casilla)
        if existing is not casilla:
            raise RegistryValidationError(
                f"m303 prorrata projection has duplicate endpoint for slot {slot} field {field!r}",
            )
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
    endpoint_by_field: dict[str, CasillaDefinition],
) -> M303ProrrataActivityRowProjection:
    """Pair one canonical row's typed values with its revision-selected endpoints."""
    return M303ProrrataActivityRowProjection(
        slot=row.slot,
        cnae=_endpoint_value(endpoint_by_field["cnae"], row.cnae_code),
        operaciones_total=_endpoint_value(endpoint_by_field["operaciones-total"], row.operaciones_total),
        operaciones_con_derecho=_endpoint_value(
            endpoint_by_field["operaciones-con-derecho"],
            row.operaciones_con_derecho,
        ),
        tipo=_endpoint_value(endpoint_by_field["tipo"], row.prorrata_type.value),
        porcentaje=_endpoint_value(endpoint_by_field["porcentaje"], row.percentage),
    )


def _endpoint_value(casilla: CasillaDefinition, value: str | Decimal) -> M303ProrrataActivityEndpointValue:
    """Validate a projected typed value against its reviewed endpoint constraints."""
    if isinstance(value, str):
        if casilla.constraints is not None and (reason := casilla.constraints.violates_text(value)) is not None:
            raise RegistryValidationError(f"m303 prorrata endpoint {casilla.id!r} rejects projected text: {reason}")
    elif casilla.constraints is not None and (reason := casilla.constraints.violates(value)) is not None:
        raise RegistryValidationError(
            f"m303 prorrata endpoint {casilla.id!r} rejects projected numeric value: {reason}",
        )
    return M303ProrrataActivityEndpointValue(casilla_id=casilla.id, value=value)


__all__ = [
    "M303ProrrataActivityEndpointValue",
    "M303ProrrataActivityRowProjection",
    "project_m303_prorrata_activity_rows",
]
