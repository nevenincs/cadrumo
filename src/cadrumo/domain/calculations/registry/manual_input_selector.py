"""Selector model for the ``manual_input`` binding source family.

Split out from :mod:`domain.calculations.registry.bindings` into its own
public defining module because :mod:`domain.calculations.registry.
binding_selector_utils` needs :class:`ManualInputProvider` while ``bindings``
imports ``selector_as_dict`` / ``selector_against_model`` FROM
``binding_selector_utils`` -- a genuine module-level import cycle that was
previously worked around with two function-local imports of a private
``bindings`` symbol.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, model_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import RegistryValidationError
from .schema_base import CasillaDataType, coerce_enum_member

__all__ = [
    "MANUAL_INPUT_RECORD_SHAPE_KEYS",
    "ManualInputDataType",
    "ManualInputProvider",
    "is_layout_binding_selector",
]

ManualInputDataType = Annotated[
    Literal[
        CasillaDataType.BOOLEAN,
        CasillaDataType.INTEGER,
        CasillaDataType.TEXT,
        CasillaDataType.DECIMAL,
        CasillaDataType.MONEY,
    ],
    BeforeValidator(coerce_enum_member(CasillaDataType)),
]
"""The scalar kinds a manual input may declare.

A narrowing of the casilla vocabulary rather than a vocabulary of its own, so a
type added there cannot leave this surface silently admitting the old set.
"""

MANUAL_INPUT_RECORD_SHAPE_KEYS: frozenset[str] = frozenset(("record", "field", "offset", "length"))
"""Canonical record-field shape keys on the manual_input selector.

Single source of truth for both the typed validator in
:class:`ManualInputProvider` and the layout-binding predicate at
:func:`is_layout_binding_selector`.
"""


def is_layout_binding_selector(selector: Mapping[str, object]) -> bool:
    """Return True when ``selector`` carries the record-field layout shape.

    The predicate intentionally mirrors the record-shape keys declared
    on :class:`ManualInputProvider` rather than re-implementing the
    check via raw key inspection. Validate gate behaviour stays
    coupled to the typed model: if the manual_input record-shape key
    set is ever extended or renamed, the layout predicate follows
    automatically.
    """
    if "data_type" not in selector:
        return False
    return MANUAL_INPUT_RECORD_SHAPE_KEYS.issubset(selector)


def _has_record_shape(selector: ManualInputProvider) -> bool:
    """Return whether any record-field coordinate was supplied."""
    return any(getattr(selector, key) is not None for key in MANUAL_INPUT_RECORD_SHAPE_KEYS)


def _validate_shape_presence(has_casilla: bool, has_record_shape: bool) -> None:
    """Enforce that exactly one manual-input selector shape is present."""
    if has_casilla and has_record_shape:
        raise RegistryValidationError(
            "manual_input selector must declare either the casilla shape or the record-field shape, not both",
        )
    if not has_casilla and not has_record_shape:
        raise RegistryValidationError("manual_input selector must declare a casilla_id or a record-field shape")


def _validate_record_shape(selector: ManualInputProvider) -> None:
    """Require every coordinate of the record-field selector shape."""
    missing = [key for key in MANUAL_INPUT_RECORD_SHAPE_KEYS if getattr(selector, key) is None]
    if missing:
        raise RegistryValidationError(
            f"manual_input record-field selector is missing required keys: {sorted(missing)!r}",
        )


def _validate_boolean_casilla_shape(selector: ManualInputProvider, has_casilla: bool) -> None:
    """Require explicit wire values for a boolean casilla selector."""
    if (
        has_casilla
        and selector.data_type == "boolean"
        and (selector.true_value is None or selector.false_value is None)
    ):
        raise RegistryValidationError(
            "manual_input boolean-casilla_id selector must declare true_value and false_value",
        )


def _validate_signed_shape(selector: ManualInputProvider, has_casilla: bool) -> None:
    """Restrict sign-marker metadata to money record-field selectors."""
    if selector.signed is not None:
        if has_casilla:
            raise RegistryValidationError(
                "manual_input casilla-shape selector cannot declare signed: the sign marker is a "
                "byte of a fixed-width record slot, which the casilla shape does not name",
            )
        if selector.signed and selector.data_type != "money":
            raise RegistryValidationError(
                f"manual_input record-field selector can declare signed only for money data, "
                f"not {selector.data_type!r}",
            )


class ManualInputProvider(BaseModel):
    """Strict validator for the selector mapping of a manual_input binding.

    Two shapes are accepted, gated by ``_validate_manual_input_shape``:

    * **Casilla shape** ``{casilla_id, data_type, true_value?, false_value?}``:
      The operator types the value directly into a registry casilla; the
      ``casilla_id`` names the canonical ``casilla.id`` and ``data_type``
      declares how the typed enum / boolean maps to the on-wire payload
      string. Used for boolean casillas like M100/0168
      (estimacion-directa modality flag).
    * **Record-field shape** ``{record, field, offset, length, data_type}``:
      The operator types a value that lands in a fichero-BOE record field
      at a specific byte offset / length. Used by M131 and other modelos
      whose bindings inject operator-typed metadata into fixed-width
      records.

    The two shapes are exclusive at the validator level.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.MANUAL_INPUT] = BindingSourceKind.MANUAL_INPUT

    # casilla shape
    casilla_id: CasillaId | None = Field(default=None, min_length=1, max_length=64)
    true_value: str | None = Field(default=None, min_length=1, max_length=64)
    false_value: str | None = Field(default=None, min_length=1, max_length=64)
    # record-field shape
    record: str | None = Field(default=None, min_length=1, max_length=64)
    field: str | None = Field(default=None, min_length=1, max_length=128)
    offset: int | None = Field(default=None, ge=1)
    length: int | None = Field(default=None, ge=1)
    # implicit-decimal scale of a record-field slot, declared per the diseno de
    # registro because the width alone does not imply it
    decimals: int | None = Field(default=None, ge=0)
    # Whether the record-field slot carries AEAT's sign marker in position 1,
    # declared per the diseno de registro: a row AEAT types ``N`` reserves that
    # byte and a row typed ``Num`` does not, and the width alone cannot say
    # which. Only meaningful for the record-field shape.
    signed: bool | None = None
    # both shapes
    data_type: ManualInputDataType

    @model_validator(mode="after")
    def _validate_manual_input_shape(self) -> ManualInputProvider:
        has_casilla = self.casilla_id is not None
        has_record_shape = _has_record_shape(self)
        _validate_shape_presence(has_casilla, has_record_shape)
        if has_record_shape:
            _validate_record_shape(self)
        # Keep these checks after shape completeness: their error order is part
        # of the registry's diagnostic contract.
        _validate_boolean_casilla_shape(self, has_casilla)
        _validate_signed_shape(self, has_casilla)
        return self
