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

A figure the operator states for a carry whose source filing lies outside the
support envelope is kept apart from both: the value stays in ``binding_overrides``
and :attr:`CalculationOperatorLayer.value_attestations` names the source filing
the statement stands in for, so verification can tell a figure stated for a
return that cannot be held from one merely typed.

A carry stated per row of a repeating group is kept in
:attr:`CalculationOperatorLayer.row_attestations`: no binding override can hold
it, because the binding fills one value per row. Each statement names the
binding and the source identity of the row it speaks of, and either states that
nothing is pending or states the amount.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import NoRecoveryOutcome
from ...core.period import RegistrySelectorPeriodCode
from ..calculations.registry.ids import BindingId
from ..identifiers import canonical_decimal_string
from .errors import ModeloOperatorLayerIntegrityError, ModeloValidatedRecord, ModeloValidationError

ATTESTED_ZERO: Final = canonical_decimal_string(Decimal(0))
"""The override an attested binding holds: the canonical zero of the decimal channel."""

OPERATOR_LAYER_IDENTITY_KEY: Final = "operator_layer"
"""The revision-identity payload key the layer contributes when it is present."""


class AttestedSource(BaseModel):
    """One earlier filing, named by modelo, filing year and registry period token."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: str = Field(min_length=1, max_length=16)
    source_filing_year: FilingYear
    source_period: RegistrySelectorPeriodCode

    def identity_payload(self) -> dict[str, object]:
        """Return the projection the revision identity hashes."""
        return {
            "source_modelo": self.source_modelo,
            "source_filing_year": self.source_filing_year,
            "source_period": self.source_period,
        }


class ValueAttestation(BaseModel):
    """The earlier filing or filings an operator-stated carry value stands in for.

    A previous-filing carry stands in for one filing, named by the three
    ``source_*`` fields. A relation-prefill carry folds several source periods,
    so ``further_sources`` names the rest; the statement then covers every one.

    Attributes:
        source_modelo: The modelo of the first earlier filing the carry would be read from.
        source_filing_year: The filing year of that earlier filing.
        source_period: The registry period token of that earlier filing.
        further_sources: Any other earlier filings the same statement covers.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: str = Field(min_length=1, max_length=16)
    source_filing_year: FilingYear
    source_period: RegistrySelectorPeriodCode
    further_sources: tuple[AttestedSource, ...] = ()

    @property
    def sources(self) -> tuple[AttestedSource, ...]:
        """Return every earlier filing this statement covers, the first one leading."""
        return (
            AttestedSource(
                source_modelo=self.source_modelo,
                source_filing_year=self.source_filing_year,
                source_period=self.source_period,
            ),
            *self.further_sources,
        )

    def identity_payload(self) -> dict[str, object]:
        """Return the projection the revision identity hashes.

        ``further_sources`` is named only when present, so a single-source
        statement keeps the identity it had before relation statements existed.
        """
        payload: dict[str, object] = {
            "source_modelo": self.source_modelo,
            "source_filing_year": self.source_filing_year,
            "source_period": self.source_period,
        }
        if self.further_sources:
            payload["further_sources"] = [source.identity_payload() for source in self.further_sources]
        return payload


class RowCarryAttestation(BaseModel):
    """The operator's statement of one row's carry: that nothing is pending, or the amount pending.

    Attributes:
        binding_id: The row binding whose registry family takes the statement.
        source_row_identity: The source identity of the row the statement speaks of.
        amount: The amount stated, as a canonical decimal string; the canonical
            zero when ``absent``.
        absent: Whether the statement is that the row carries nothing, rather
            than a figure typed.
    """

    model_config = STRICT_FROZEN_CONFIG

    binding_id: BindingId
    source_row_identity: str = Field(min_length=1, max_length=256)
    amount: str = Field(min_length=1, max_length=64)
    absent: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_a_canonical_amount(self) -> RowCarryAttestation:
        parsed = try_parse_canonical_decimal(self.amount)
        if parsed is None or canonical_decimal_string(parsed) != self.amount or parsed < 0:
            raise ModeloOperatorLayerIntegrityError(
                f"operator layer row statement on {self.binding_id!r} must hold a canonical nonnegative amount",
                translated_message="errors.integrity.operator_layer_value_attestation_not_canonical",
                context={"binding_id": self.binding_id},
            )
        if self.absent and self.amount != ATTESTED_ZERO:
            raise ModeloOperatorLayerIntegrityError(
                f"operator layer row statement of absence on {self.binding_id!r} must hold the attested zero",
                translated_message="errors.integrity.operator_layer_attestation_kinds_conflict",
                context={"binding_id": self.binding_id},
            )
        return self

    @property
    def key(self) -> tuple[BindingId, str]:
        """Return the binding and row this statement speaks of; a layer holds one statement per key."""
        return self.binding_id, self.source_row_identity

    @property
    def stated_amount(self) -> Decimal:
        """Return the amount the statement puts on its row; zero for a statement of absence."""
        return Decimal(self.amount)

    def identity_payload(self) -> dict[str, object]:
        """Return the projection the revision identity hashes."""
        return {
            "binding_id": self.binding_id,
            "source_row_identity": self.source_row_identity,
            "amount": self.amount,
            "absent": self.absent,
        }


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
        value_attestations: The bindings whose canonical decimal override is
            the operator's stated figure for an earlier filing the product cannot
            hold, keyed by binding id, each naming that filing. A binding is never
            both here and in ``attested_binding_ids``.
        row_attestations: The operator's statements of a carry on one row of a
            repeating group, one per binding and row, in key order.
    """

    model_config = STRICT_FROZEN_CONFIG

    decimal_casilla_inputs: Mapping[CasillaId, str] = Field(default_factory=dict)
    text_casilla_inputs: Mapping[CasillaId, str] = Field(default_factory=dict)
    binding_overrides: Mapping[BindingId, str] = Field(default_factory=dict)
    attested_binding_ids: tuple[BindingId, ...] = ()
    value_attestations: Mapping[BindingId, ValueAttestation] = Field(default_factory=dict)
    row_attestations: tuple[RowCarryAttestation, ...] = ()

    def _require_casilla_channels_canonical(self) -> None:
        overlapping = sorted(set(self.decimal_casilla_inputs).intersection(self.text_casilla_inputs))
        if overlapping:
            raise ModeloValidationError(
                f"operator layer casillas must reach exactly one channel; both channels carry {overlapping!r}",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.CALCULATION_REVISION,
            )
        for casilla_id, raw in self.decimal_casilla_inputs.items():
            parsed = try_parse_canonical_decimal(raw)
            if parsed is None or canonical_decimal_string(parsed) != raw:
                raise ModeloValidationError(
                    f"operator layer decimal input for casilla {casilla_id!r} is not a canonical decimal string",
                    no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                    record=ModeloValidatedRecord.CALCULATION_REVISION,
                )

    def _require_attested_bindings_hold_zero(self) -> tuple[BindingId, ...]:
        attested = self.attested_binding_ids
        if list(attested) != sorted(set(attested)):
            raise ModeloValidationError(
                "operator layer attested bindings must be unique and sorted",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.CALCULATION_REVISION,
            )
        for binding_id in attested:
            if self.binding_overrides.get(binding_id) != ATTESTED_ZERO:
                raise ModeloValidationError(
                    f"operator layer attested binding {binding_id!r} must hold the attested zero override",
                    no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                    record=ModeloValidatedRecord.CALCULATION_REVISION,
                )
        return attested

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_channel_unique_canonical_values(self) -> CalculationOperatorLayer:
        self._require_casilla_channels_canonical()
        attested = self._require_attested_bindings_hold_zero()
        for binding_id in self.value_attestations:
            raw = self.binding_overrides.get(binding_id)
            parsed = None if raw is None else try_parse_canonical_decimal(raw)
            if parsed is None or canonical_decimal_string(parsed) != raw:
                raise ModeloOperatorLayerIntegrityError(
                    f"operator layer value-attested binding {binding_id!r} must hold a canonical decimal override",
                    translated_message="errors.integrity.operator_layer_value_attestation_not_canonical",
                    context={"binding_id": binding_id},
                )
            if binding_id in attested:
                raise ModeloOperatorLayerIntegrityError(
                    f"operator layer binding {binding_id!r} cannot be both attested as no amount and value-attested",
                    translated_message="errors.integrity.operator_layer_attestation_kinds_conflict",
                    context={"binding_id": binding_id},
                )
        keys = [statement.key for statement in self.row_attestations]
        if keys != sorted(set(keys)):
            raise ModeloValidationError("operator layer row statements must be unique per binding and row, in order")
        return self

    @property
    def is_empty(self) -> bool:
        """Whether the operator authored no value at all in this calculation."""
        return not (
            self.decimal_casilla_inputs or self.text_casilla_inputs or self.binding_overrides or self.row_attestations
        )

    def casilla_ids(self) -> frozenset[CasillaId]:
        """Every casilla the operator set a value on, whatever its channel."""
        return frozenset(self.decimal_casilla_inputs) | frozenset(self.text_casilla_inputs)

    def identity_payload(self) -> dict[str, object]:
        """Return the order-canonical projection the revision identity hashes.

        Attested bindings, value attestations and row statements are named only
        when there are any, so a layer that attests nothing keeps the identity it had before
        attestations existed.
        """
        payload: dict[str, object] = {
            "decimal_casilla_inputs": dict(sorted(self.decimal_casilla_inputs.items())),
            "text_casilla_inputs": dict(sorted(self.text_casilla_inputs.items())),
            "binding_overrides": dict(sorted(self.binding_overrides.items())),
        }
        if self.attested_binding_ids:
            payload["attested_binding_ids"] = list(self.attested_binding_ids)
        if self.value_attestations:
            payload["value_attestations"] = {
                binding_id: attestation.identity_payload()
                for binding_id, attestation in sorted(self.value_attestations.items())
            }
        if self.row_attestations:
            payload["row_attestations"] = [statement.identity_payload() for statement in self.row_attestations]
        return payload


__all__ = [
    "ATTESTED_ZERO",
    "OPERATOR_LAYER_IDENTITY_KEY",
    "AttestedSource",
    "CalculationOperatorLayer",
    "RowCarryAttestation",
    "ValueAttestation",
]
