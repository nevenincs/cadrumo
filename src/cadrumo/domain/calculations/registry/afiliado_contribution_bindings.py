"""Declared source fields for the annual Modelo 156 affiliate calendar.

The record design owns byte positions. This provider identifies typed source
facts only; it does not turn a scalar manual-input binding into a row set.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, model_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import RegistryValidationError

if TYPE_CHECKING:
    from .schema import BindingDefinition


class AfiliadoContributionProvider(BaseModel):
    """One independent identity or month fact from an explicitly supplied member."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.AFILIADO_COTIZACION] = BindingSourceKind.AFILIADO_COTIZACION
    fact: Literal["row_field"]
    target_casilla_id: CasillaId
    row_field: str = Field(pattern=r"^(nif|nombre|numero_afiliacion|cotizacion_(0[1-9]|1[0-2])_(situacion|importe))$")
    grouping: Literal["per_member"]
    record: Literal["afiliado"]
    data_type: Literal["text", "money"]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _source_type_matches_field(self) -> AfiliadoContributionProvider:
        expected = "money" if self.row_field.endswith("_importe") else "text"
        if self.data_type != expected:
            raise RegistryValidationError("affiliate source field and declared scalar type disagree")
        return self


def validate_afiliado_contribution_binding(binding: BindingDefinition) -> list[str]:
    """Keep the binding value contract aligned with the typed source field."""
    provider = binding.provider
    if not isinstance(provider, AfiliadoContributionProvider):
        return ["affiliate binding requires its typed provider"]
    if binding.value.data_type != provider.data_type:
        return ["affiliate binding value type disagrees with its source field"]
    return []
