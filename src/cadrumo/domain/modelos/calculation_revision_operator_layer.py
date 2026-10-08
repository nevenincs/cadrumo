"""The operator-authored inputs of one calculation revision, kept apart from every source tier.

A revision's ``input_values_by_casilla_id`` and ``binding_overrides`` merge the
declaration-period, backend, bound, profile, borrador and caller values into one
replay map, so neither can say which entries the operator typed. Replaying them
as the next caller tier would freeze ledger, profile and borrador values as
operator overrides that outrank every later source. The operator layer records
the caller tier on its own, so the next calculation can start from exactly what
the operator authored and nothing else.

The layer is optional on a revision. A revision stored before the layer existed
carries none, and that absence means the operator layer is UNKNOWN for it,
never that the operator authored nothing: :attr:`CalculationOperatorLayer`
instances are only ever constructed from a calculation that knew its caller
tier. The explicit clears the operator made live on the revision's existing
``cleared_casilla_ids`` axis, which already records them for every revision;
the layer holds the values.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.ids import BindingId
from ..identifiers import canonical_decimal_string
from .errors import ModeloValidationError

OPERATOR_LAYER_IDENTITY_KEY: Final = "operator_layer"
"""The revision-identity payload key the layer contributes when it is present."""


class CalculationOperatorLayer(BaseModel):
    """The values the operator authored for one calculation, split by the engine channel they reach.

    Attributes:
        decimal_casilla_inputs: Casilla values the operator set on the decimal
            channel (money, decimal, integer, ratio, and boolean encoded 0/1),
            as canonical decimal strings.
        text_casilla_inputs: Casilla values the operator set on the text
            channel, as the canonical text the registry validator returned.
        binding_overrides: Binding values the operator set, as the canonical
            string each binding's declared channel accepts (a canonical decimal
            for a decimal channel, the member token for an enum channel).
    """

    model_config = STRICT_FROZEN_CONFIG

    decimal_casilla_inputs: Mapping[CasillaId, str] = Field(default_factory=dict)
    text_casilla_inputs: Mapping[CasillaId, str] = Field(default_factory=dict)
    binding_overrides: Mapping[BindingId, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_channel_unique_canonical_values(self) -> CalculationOperatorLayer:
        overlapping = sorted(set(self.decimal_casilla_inputs).intersection(self.text_casilla_inputs))
        if overlapping:
            raise ModeloValidationError(
                f"operator layer casillas must reach exactly one channel; both channels carry {overlapping!r}",
            )
        for casilla_id, raw in self.decimal_casilla_inputs.items():
            parsed = try_parse_canonical_decimal(raw)
            if parsed is None or canonical_decimal_string(parsed) != raw:
                raise ModeloValidationError(
                    f"operator layer decimal input for casilla {casilla_id!r} is not a canonical decimal string",
                )
        return self

    @property
    def is_empty(self) -> bool:
        """Whether the operator authored no value at all in this calculation."""
        return not (self.decimal_casilla_inputs or self.text_casilla_inputs or self.binding_overrides)

    def casilla_ids(self) -> frozenset[CasillaId]:
        """Every casilla the operator set a value on, whatever its channel."""
        return frozenset(self.decimal_casilla_inputs) | frozenset(self.text_casilla_inputs)

    def identity_payload(self) -> dict[str, object]:
        """Return the order-canonical projection the revision identity hashes."""
        return {
            "decimal_casilla_inputs": dict(sorted(self.decimal_casilla_inputs.items())),
            "text_casilla_inputs": dict(sorted(self.text_casilla_inputs.items())),
            "binding_overrides": dict(sorted(self.binding_overrides.items())),
        }


__all__ = ["OPERATOR_LAYER_IDENTITY_KEY", "CalculationOperatorLayer"]
