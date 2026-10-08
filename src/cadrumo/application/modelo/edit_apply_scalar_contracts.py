"""Lossless scalar, binding and materialized row edit intent contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field

from .edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditRowAddressV1,
    ModeloEditRowIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloRowEditIntentV1,
    ModeloScalarEditIntentV1,
)

if TYPE_CHECKING:
    from ...domain.filing.schema import ModeloScalar


#: Wire-safe mirror of ``ModeloScalar`` (``Decimal | int | str | bool | date | None``).
#: ``Decimal`` validates from a JSON number OR a pattern-matched string but
#: always SERIALIZES back to a string, so a field typed ``ModeloScalar``
#: fails the operations payload-graph gate's validation/serialization
#: schema-identity check. Dropping the raw ``Decimal`` input option and
#: requiring a decimal amount to arrive as a string - exactly what
#: serialization already produces, and what real fixtures already pass
#: (``value="150.00"``) - removes the asymmetry with no loss of expressible
#: values, though NOT where this once said. ``to_submission`` does not restore
#: the ``Decimal``: ``ModeloScalar`` is a plain union and ``EditModel`` is
#: strict, so a string crosses back as a string. The reconstruction happens one
#: layer further in, at the execution boundary, which re-applies the address's
#: admitted value grammar (the registry's declared type, precision and bounds)
#: rather than trusting the value's Python type. That is the stronger
#: guarantee -- the registry decides what a casilla holds, not the wire -- but
#: it does mean a round trip through this mirror is not an identity for
#: ``Decimal``, and a test asserting that it is will fail correctly.
type _ModeloEditApplyScalarValue = int | str | bool | date | None


def _wire_scalar_value(value: ModeloScalar) -> _ModeloEditApplyScalarValue:
    """Mirror one domain ``ModeloScalar`` onto the payload-safe wire union.

    Only ``Decimal`` needs mirroring, and it becomes the exact characters
    ``str`` produces -- which is precisely what serialization already emits
    and what ``to_intent`` parses back. Every other member of ``ModeloScalar``
    is already a member of the wire union and crosses unchanged.

    Not a total inverse of the round trip, deliberately. ``ModeloScalar``
    admits a plain ``str``, so a string that spells a number is
    indistinguishable on the wire from a ``Decimal`` and comes back as a
    ``str``. Nothing is lost by that: the execution boundary reads the value
    again through the address's admitted grammar, so what a casilla holds is
    decided by the registry rather than by which Python type happened to
    survive the trip.
    """
    return str(value) if isinstance(value, Decimal) else value


class ModeloEditApplyScalarIntentV1(BaseModel):
    """Wire mirror of ModeloScalarEditIntentV1 with a payload-safe value."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    address: ModeloEditScalarAddressV1
    kind: ModeloEditScalarIntentKind
    value: _ModeloEditApplyScalarValue = None

    def to_intent(self) -> ModeloScalarEditIntentV1:
        """Translate back to the real, fully re-validated domain intent."""
        return ModeloScalarEditIntentV1(address=self.address, kind=self.kind, value=self.value)

    @classmethod
    def from_intent(cls, intent: ModeloScalarEditIntentV1) -> ModeloEditApplyScalarIntentV1:
        """Mirror a domain scalar intent onto the wire form ``to_intent`` reverses."""
        return cls(address=intent.address, kind=intent.kind, value=_wire_scalar_value(intent.value))


class ModeloEditApplyBindingIntentV1(BaseModel):
    """Wire mirror of ModeloBindingEditIntentV1 with a payload-safe value."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    address: ModeloEditBindingAddressV1
    kind: ModeloEditBindingIntentKind
    value: _ModeloEditApplyScalarValue = None

    def to_intent(self) -> ModeloBindingEditIntentV1:
        """Translate back to the real, fully re-validated domain intent."""
        return ModeloBindingEditIntentV1(address=self.address, kind=self.kind, value=self.value)

    @classmethod
    def from_intent(cls, intent: ModeloBindingEditIntentV1) -> ModeloEditApplyBindingIntentV1:
        """Mirror a domain binding intent onto the wire form ``to_intent`` reverses."""
        return cls(address=intent.address, kind=intent.kind, value=_wire_scalar_value(intent.value))


class ModeloEditApplyRowIntentV1(BaseModel):
    """Wire mirror of ModeloRowEditIntentV1 with payload-safe row values."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    address: ModeloEditRowAddressV1
    kind: ModeloEditRowIntentKind
    row: Annotated[tuple[ModeloEditApplyScalarIntentV1, ...], Field(max_length=200)] | None = None
    move_to_index: Annotated[int, Field(ge=1)] | None = None

    def to_intent(self) -> ModeloRowEditIntentV1:
        """Translate back to the real, fully re-validated domain intent."""
        return ModeloRowEditIntentV1(
            address=self.address,
            kind=self.kind,
            row=None if self.row is None else tuple(entry.to_intent() for entry in self.row),
            move_to_index=self.move_to_index,
        )

    @classmethod
    def from_intent(cls, intent: ModeloRowEditIntentV1) -> ModeloEditApplyRowIntentV1:
        """Mirror a domain row intent, including each of its scalar entries."""
        return cls(
            address=intent.address,
            kind=intent.kind,
            row=(
                None
                if intent.row is None
                else tuple(ModeloEditApplyScalarIntentV1.from_intent(entry) for entry in intent.row)
            ),
            move_to_index=intent.move_to_index,
        )
