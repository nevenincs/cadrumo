"""The provider that reads one fact of one prorrata activity row from the profile's register.

The Modelo 390 apartado 12 prints, for each of five activity rows, the CNAE
code, the volume of operations, the volume with the right to deduct, the kind
of prorrata and its definitive percentage. Those are durable children of the
encrypted :class:`~cadrumo.domain.prorrata_register.register.ProrrataRegister`,
the same rows the Modelo 303 reads; a binding of this kind names the row slot
and the fact, and the resolver supplies the value. No operator input channel
duplicates them.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Final, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from ....core.aggregation import BindingSourceKind
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_selector_utils import selector_against_model
from .binding_value_contract import BindingValueChannel
from .errors import RegistryValidationError
from .form_codes import exceeds_form_bound
from .schema_base import coerce_enum_member

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .schema import BindingDefinition

__all__ = [
    "PRORRATA_ACTIVITY_FIELD_CHANNEL",
    "ProrrataActivityField",
    "ProrrataRegisterActivityProvider",
    "validate_prorrata_register_activity_binding",
]


class ProrrataActivityField(StrEnum):
    """The closed facts one register activity row carries to an official box."""

    CNAE = "cnae"
    OPERACIONES_TOTAL = "operaciones_total"
    OPERACIONES_CON_DERECHO = "operaciones_con_derecho"
    TIPO = "tipo"
    PORCENTAJE = "porcentaje"


PRORRATA_ACTIVITY_FIELD_CHANNEL: Final[Mapping[ProrrataActivityField, BindingValueChannel]] = MappingProxyType(
    {
        ProrrataActivityField.CNAE: BindingValueChannel.TEXT,
        ProrrataActivityField.OPERACIONES_TOTAL: BindingValueChannel.DECIMAL,
        ProrrataActivityField.OPERACIONES_CON_DERECHO: BindingValueChannel.DECIMAL,
        ProrrataActivityField.TIPO: BindingValueChannel.TEXT,
        ProrrataActivityField.PORCENTAJE: BindingValueChannel.DECIMAL,
    },
)
"""The value channel each fact travels: codes as text, amounts and the percentage as decimals.

A CNAE code is text because its leading zeros are part of the code.
"""


class ProrrataRegisterActivityProvider(BaseModel):
    """One fact of one fixed activity row of the prorrata register."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.PRORRATA_REGISTER_ACTIVITY] = BindingSourceKind.PRORRATA_REGISTER_ACTIVITY
    row: str = Field(pattern=r"^[1-9][0-9]*$")
    """The register row slot, as the form numbers it.

    Authored as text because it names a row of the official grid, not a filing
    coordinate; :attr:`slot` is the same number for the register lookup.
    """
    field: Annotated[ProrrataActivityField, BeforeValidator(coerce_enum_member(ProrrataActivityField))]

    @field_validator("row")
    @classmethod
    @pydantic_validation_boundary
    def _row_is_a_declared_slot(cls, row: str) -> str:
        if exceeds_form_bound(int(row), "m303.prorrata.activity_slots"):
            raise RegistryValidationError(f"prorrata activity row {row} is past the form's declared rows")
        return row

    @property
    def slot(self) -> int:
        """Return the register slot this binding reads."""
        return int(self.row)


def validate_prorrata_register_activity_binding(binding: BindingDefinition) -> list[str]:
    """Return the build-time diagnostics for one prorrata activity binding.

    The fact fixes the value channel, and the resolver reads one row's fact
    directly, so no aggregation may be authored over it.
    """
    failures = selector_against_model(binding, ProrrataRegisterActivityProvider)
    provider = binding.provider
    if isinstance(provider, ProrrataRegisterActivityProvider):
        expected = PRORRATA_ACTIVITY_FIELD_CHANNEL[provider.field]
        if binding.value.channel is not expected:
            failures.append(
                f"binding {binding.id!r} prorrata activity fact {provider.field.value!r} travels the "
                f"{expected.value!r} channel, not {binding.value.channel.value!r}",
            )
    if binding.aggregation is not None:
        failures.append(
            f"binding {binding.id!r} reads one register row fact, so no aggregation may be authored",
        )
    return failures
