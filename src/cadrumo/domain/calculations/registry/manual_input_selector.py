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
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, model_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_value_contract import CHANNEL_FOR_BINDING_DATA_TYPE, BindingDataType
from .errors import RegistryValidationError
from .schema_base import CasillaDataType, coerce_enum_member

if TYPE_CHECKING:
    from .schema import BindingDefinition

__all__ = [
    "MANUAL_INPUT_RECORD_SHAPE_KEYS",
    "ManualInputDataType",
    "ManualInputProvider",
    "is_layout_binding_selector",
    "validate_manual_input_binding",
]

ManualInputDataType = Annotated[
    Literal[
        CasillaDataType.BOOLEAN,
        CasillaDataType.INTEGER,
        CasillaDataType.TEXT,
        CasillaDataType.DECIMAL,
        CasillaDataType.MONEY,
        CasillaDataType.DATE,
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


def _validate_decimal_scale(selector: ManualInputProvider, has_record_shape: bool) -> None:
    """Require a record-field slot to declare its implicit scale exactly when it is decimal."""
    if selector.data_type == "decimal":
        if has_record_shape and selector.decimals is None:
            raise RegistryValidationError("manual_input decimal record-field selector must declare decimals")
    elif selector.decimals is not None:
        raise RegistryValidationError(
            f"manual_input selector declares decimals but its data_type is {str(selector.data_type)!r}",
        )


class ManualInputProvider(BaseModel):
    """Strict validator for the selector mapping of a manual_input binding.

    Two shapes are accepted, gated by ``_validate_manual_input_shape``:

    * **Casilla shape** ``{casilla_id, data_type}``:
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
    @pydantic_validation_boundary
    def _validate_manual_input_shape(self) -> ManualInputProvider:
        has_casilla = self.casilla_id is not None
        has_record_shape = _has_record_shape(self)
        _validate_shape_presence(has_casilla, has_record_shape)
        if has_record_shape:
            _validate_record_shape(self)
        # Keep these checks after shape completeness: their error order is part
        # of the registry's diagnostic contract.
        _validate_signed_shape(self, has_casilla)
        _validate_decimal_scale(self, has_record_shape)
        return self


def validate_manual_input_binding(binding: BindingDefinition) -> list[str]:
    """Return the build-time diagnostics for one manual_input binding.

    The wire ``data_type`` describes how the typed value is encoded, and the
    binding's value channel is what a consumer narrows on. The two are declared
    independently, so the canonical data-type-to-channel pairing is what refuses
    a binding whose operator input would travel on a carrier its wire encoding
    cannot fill. The wire type and the value type may legitimately differ (a
    decimal encoding of a money quantity), so only the carrier is compared.
    """
    provider = binding.provider
    if not isinstance(provider, ManualInputProvider):
        return [f"binding {binding.id!r} (source={binding.source!r}) is not a manual_input provider"]
    expected = CHANNEL_FOR_BINDING_DATA_TYPE[BindingDataType(str(provider.data_type))]
    if binding.value.channel is expected:
        return []
    return [
        f"binding {binding.id!r} (source={binding.source!r}) manual-input invariants violated: "
        f"wire data_type {str(provider.data_type)!r} travels the {expected.value!r} channel, "
        f"not {binding.value.channel.value!r}",
    ]
