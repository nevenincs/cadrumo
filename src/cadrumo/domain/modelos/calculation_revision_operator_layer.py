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

A binding the operator attested holds no amount is kept apart from a zero the
operator typed: its override is zero and the binding is named in
:attr:`CalculationOperatorLayer.attested_binding_ids`, so verification can tell a
statement that nothing is pending from a figure entered and from a value missing.
A layer stored before attestations existed names none, which means none was made.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.ids import BindingId
from ..identifiers import canonical_decimal_string
from .errors import ModeloValidationError

ATTESTED_ZERO: Final = canonical_decimal_string(Decimal(0))
"""The override an attested binding holds: the canonical zero of the decimal channel."""

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
        attested_binding_ids: The bindings whose override is the operator's
            statement that they hold no amount, rather than a zero typed, in
            sorted order; each holds :data:`ATTESTED_ZERO` in ``binding_overrides``.
    """

    model_config = STRICT_FROZEN_CONFIG

    decimal_casilla_inputs: Mapping[CasillaId, str] = Field(default_factory=dict)
    text_casilla_inputs: Mapping[CasillaId, str] = Field(default_factory=dict)
    binding_overrides: Mapping[BindingId, str] = Field(default_factory=dict)
    attested_binding_ids: tuple[BindingId, ...] = ()

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
        attested = self.attested_binding_ids
        if list(attested) != sorted(set(attested)):
            raise ModeloValidationError("operator layer attested bindings must be unique and sorted")
        for binding_id in attested:
            if self.binding_overrides.get(binding_id) != ATTESTED_ZERO:
                raise ModeloValidationError(
                    f"operator layer attested binding {binding_id!r} must hold the attested zero override",
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
        """Return the order-canonical projection the revision identity hashes.

        Attested bindings are named only when there are any, so a layer that
        attests nothing keeps the identity it had before attestations existed.
        """
        payload: dict[str, object] = {
            "decimal_casilla_inputs": dict(sorted(self.decimal_casilla_inputs.items())),
            "text_casilla_inputs": dict(sorted(self.text_casilla_inputs.items())),
            "binding_overrides": dict(sorted(self.binding_overrides.items())),
        }
        if self.attested_binding_ids:
            payload["attested_binding_ids"] = list(self.attested_binding_ids)
        return payload


__all__ = ["ATTESTED_ZERO", "OPERATOR_LAYER_IDENTITY_KEY", "CalculationOperatorLayer"]
