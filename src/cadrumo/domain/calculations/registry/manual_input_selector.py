"""Selector model for the ``manual_input`` binding source family.

Split out from :mod:`domain.calculations.registry.bindings` into its own
public defining module because :mod:`domain.calculations.registry.
binding_selector_utils` needs :class:`ManualInputSelector` while ``bindings``
imports ``selector_as_dict`` / ``selector_against_model`` FROM
``binding_selector_utils`` -- a genuine module-level import cycle that was
previously worked around with two function-local imports of a private
``bindings`` symbol.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.casilla_id import CasillaId
from .errors import RegistryValidationError

__all__ = [
    "MANUAL_INPUT_RECORD_SHAPE_KEYS",
    "ManualInputDataType",
    "ManualInputSelector",
    "is_layout_binding_selector",
]

ManualInputDataType = Literal["boolean", "integer", "text", "decimal", "money"]

MANUAL_INPUT_RECORD_SHAPE_KEYS: frozenset[str] = frozenset(("record", "field", "offset", "length"))
"""Canonical record-field shape keys on the manual_input selector.

Single source of truth for both the typed validator in
:class:`ManualInputSelector` and the layout-binding predicate at
:func:`is_layout_binding_selector`.
"""


def is_layout_binding_selector(selector: Mapping[str, object]) -> bool:
    """Return True when ``selector`` carries the record-field layout shape.

    The predicate intentionally mirrors the record-shape keys declared
    on :class:`ManualInputSelector` rather than re-implementing the
    check via raw key inspection. Validate gate behaviour stays
    coupled to the typed model: if the manual_input record-shape key
    set is ever extended or renamed, the layout predicate follows
    automatically.
    """
    if "data_type" not in selector:
        return False
    return MANUAL_INPUT_RECORD_SHAPE_KEYS.issubset(selector)


class ManualInputSelector(BaseModel):
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
    def _validate_manual_input_shape(self) -> ManualInputSelector:
        record_shape_keys = MANUAL_INPUT_RECORD_SHAPE_KEYS
        has_casilla = self.casilla_id is not None
        has_record_shape = any(getattr(self, key) is not None for key in record_shape_keys)
        if has_casilla and has_record_shape:
            raise RegistryValidationError(
                "manual_input selector must declare either the casilla shape or the record-field shape, not both",
            )
        if not has_casilla and not has_record_shape:
            raise RegistryValidationError("manual_input selector must declare a casilla_id or a record-field shape")
        if has_record_shape:
            missing = [key for key in record_shape_keys if getattr(self, key) is None]
            if missing:
                raise RegistryValidationError(
                    f"manual_input record-field selector is missing required keys: {sorted(missing)!r}",
                )
        # Boolean casilla shape always pairs the data_type with explicit
        # true_value / false_value strings so the on-wire encoding is
        # deterministic.
        if has_casilla and self.data_type == "boolean" and (self.true_value is None or self.false_value is None):
            raise RegistryValidationError(
                "manual_input boolean-casilla_id selector must declare true_value and false_value",
            )
        if self.signed is not None:
            # The sign marker is a byte of the fixed-width slot, so it is only
            # meaningful where the selector names one.
            if has_casilla:
                raise RegistryValidationError(
                    "manual_input casilla-shape selector cannot declare signed: the sign marker is a "
                    "byte of a fixed-width record slot, which the casilla shape does not name",
                )
            if self.signed and self.data_type != "money":
                raise RegistryValidationError(
                    f"manual_input record-field selector can declare signed only for money data, "
                    f"not {self.data_type!r}",
                )
        return self
