"""The value-free entry grammar of one writable Modelo edit address.

Admission projects a :class:`ModeloEditValueGrammarV1` onto every writable
casilla and binding-override entry, so an editor knows -- before any value is
typed -- which value family an address takes, which engine channel will carry
it, and which registry-declared constraints the value must satisfy. The
grammar carries registry metadata only, never a taxpayer value, so it is safe
inside the edit baseline.

The parser (:mod:`.edit_parsing`) reads lexemes against this grammar, and the
edit executor re-applies the same typed half to every submitted value, so a
value that passes the parser passes the engine.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Final

from pydantic import Field

from ...domain.calculations.registry.binding_value_contract import BindingDataType, BindingValueChannel
from ...domain.calculations.registry.runtime_graph import enum_consumed_binding_ids, revision_date_binding_ids
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ...domain.calculations.registry.schema_base import (
    CasillaDataType,
    CasillaSignConstraint,
    CasillaSignConstraintValue,
)
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.identifiers import canonical_decimal_string
from .edit_contract import EditModel

MONEY_FRACTION_DIGITS: Final = 2
"""A euro amount is entered in cents at most; the parser never rounds a finer value."""

MONEY_OPERAND_MAXIMUM: Final = Decimal("999999999999.99")
"""The magnitude bound of one hand-entered euro amount, applied to money addresses only.

The manual-override financial-operand declaration of the edit operation states
the same bound from here, so the parser, the executor and the wire cannot
disagree about which amounts an operator may enter.
"""

type _BoundedToken = Annotated[str, Field(min_length=1, max_length=128)]
type _CanonicalDecimal = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^-?\d+(\.\d+)?$")]
"""A registry bound as canonical decimal text, so the grammar crosses an operation payload unchanged."""


class ModeloEditValueFamily(StrEnum):
    """The kind of value an address takes, independent of how it is written."""

    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    TEXT = "text"


class ModeloEditValueChannel(StrEnum):
    """Which engine input channel carries the value; ``UNAVAILABLE`` means none does yet."""

    DECIMAL = "decimal"
    TEXT = "text"
    UNAVAILABLE = "unavailable"


class ModeloEditRatioUnit(StrEnum):
    """How a ratio value is read, where the registry lets it be known.

    The registry declares no unit for a ratio; only its bounds can tell a
    percentage (declared maximum 100) from a fraction (declared maximum 1). A
    ratio with neither is ``UNDECLARED`` and an editor must say so rather than
    guess a hundredfold.
    """

    PERCENT = "percent"
    FRACTION = "fraction"
    UNDECLARED = "undeclared"


class ModeloEditChoiceV1(EditModel):
    """One registry-declared choice: the stored code, never translated."""

    code: _BoundedToken


class ModeloEditValueGrammarV1(EditModel):
    """Everything an editor and the parser need to read one address's value; carries no value.

    ``data_type`` is the registry token of the address (a casilla data type,
    or a binding value data type). ``minimum`` and ``maximum`` are canonical
    decimal text; :meth:`minimum_value` and :meth:`maximum_value` read them.
    ``max_fraction_digits`` is ``None`` when the registry states no precision. ``pattern`` is the registry-declared text
    pattern, used for validation and never shown. ``constraints_declared`` is
    false for the common case of an address whose registry row states no
    constraint at all, which an editor shows as such.
    """

    data_type: _BoundedToken
    family: ModeloEditValueFamily
    channel: ModeloEditValueChannel
    max_fraction_digits: Annotated[int, Field(ge=0)] | None = None
    sign: CasillaSignConstraintValue = CasillaSignConstraint.ANY
    minimum: _CanonicalDecimal | None = None
    maximum: _CanonicalDecimal | None = None
    choices: tuple[ModeloEditChoiceV1, ...] | None = None
    min_length: Annotated[int, Field(ge=0)] | None = None
    max_length: Annotated[int, Field(ge=0)] | None = None
    pattern: Annotated[str, Field(min_length=1, max_length=512)] | None = None
    ratio_unit: ModeloEditRatioUnit | None = None
    money_operand_bound: bool = False
    required: bool = False
    constraints_declared: bool = False

    def minimum_value(self) -> Decimal | None:
        """The declared lower bound as a decimal, or ``None`` when none is declared."""
        return None if self.minimum is None else Decimal(self.minimum)

    def maximum_value(self) -> Decimal | None:
        """The declared upper bound as a decimal, or ``None`` when none is declared."""
        return None if self.maximum is None else Decimal(self.maximum)

    @property
    def writable(self) -> bool:
        """Whether an engine channel exists to carry a value of this grammar."""
        return self.channel is not ModeloEditValueChannel.UNAVAILABLE


_DECIMAL_FAMILY_TYPES: Final = frozenset({CasillaDataType.MONEY, CasillaDataType.DECIMAL, CasillaDataType.RATIO})


def _casilla_family_and_channel(data_type: str) -> tuple[ModeloEditValueFamily, ModeloEditValueChannel]:
    if data_type in _DECIMAL_FAMILY_TYPES:
        return ModeloEditValueFamily.DECIMAL, ModeloEditValueChannel.DECIMAL
    if data_type == CasillaDataType.INTEGER:
        return ModeloEditValueFamily.INTEGER, ModeloEditValueChannel.DECIMAL
    if data_type == CasillaDataType.BOOLEAN:
        # The engine reads a boolean casilla on its decimal channel, encoded 0 / 1.
        return ModeloEditValueFamily.BOOLEAN, ModeloEditValueChannel.DECIMAL
    if data_type == CasillaDataType.YEAR:
        return ModeloEditValueFamily.INTEGER, ModeloEditValueChannel.UNAVAILABLE
    if data_type == CasillaDataType.DATE:
        return ModeloEditValueFamily.DATE, ModeloEditValueChannel.UNAVAILABLE
    return ModeloEditValueFamily.TEXT, ModeloEditValueChannel.TEXT


def _ratio_unit(data_type: str, maximum: Decimal | None) -> ModeloEditRatioUnit | None:
    if data_type != CasillaDataType.RATIO:
        return None
    if maximum == Decimal(100):
        return ModeloEditRatioUnit.PERCENT
    if maximum == Decimal(1):
        return ModeloEditRatioUnit.FRACTION
    return ModeloEditRatioUnit.UNDECLARED


def casilla_value_grammar(casilla: CasillaDefinition) -> ModeloEditValueGrammarV1:
    """Project one casilla definition onto its entry grammar."""
    data_type = str(casilla.data_type)
    family, channel = _casilla_family_and_channel(data_type)
    constraints = casilla.constraints
    is_money = data_type == CasillaDataType.MONEY
    fraction_digits: int | None = MONEY_FRACTION_DIGITS if is_money else None
    if family is ModeloEditValueFamily.INTEGER:
        fraction_digits = 0
    maximum = constraints.max_value if constraints is not None else None
    minimum = constraints.min_value if constraints is not None else None
    return ModeloEditValueGrammarV1(
        data_type=data_type,
        family=family,
        channel=channel,
        max_fraction_digits=fraction_digits,
        sign=constraints.sign if constraints is not None else CasillaSignConstraint.ANY,
        minimum=None if minimum is None else canonical_decimal_string(minimum),
        maximum=None if maximum is None else canonical_decimal_string(maximum),
        choices=(
            tuple(ModeloEditChoiceV1(code=token) for token in constraints.enum)
            if constraints is not None and constraints.enum is not None
            else None
        ),
        min_length=constraints.min_length if constraints is not None else None,
        max_length=constraints.max_length if constraints is not None else None,
        pattern=constraints.pattern if constraints is not None else None,
        ratio_unit=_ratio_unit(data_type, maximum),
        money_operand_bound=is_money,
        required=casilla.required,
        constraints_declared=constraints is not None,
    )


_BINDING_DECIMAL_TYPES: Final = frozenset(
    {BindingDataType.MONEY, BindingDataType.DECIMAL, BindingDataType.INTEGER, BindingDataType.BOOLEAN}
)


def binding_value_grammar(binding: BindingDefinition, *, revision: ModeloRevision) -> ModeloEditValueGrammarV1:
    """Project one binding onto the entry grammar of its override.

    The override reaches the engine the way the explicit ``--binding`` path
    routes it: a binding the revision's formulas read as an enum key takes its
    token verbatim, a decimal, integer or boolean binding takes a decimal
    (boolean encoded 0 / 1), and a date-consumed, row-set, or free-text binding
    has no override channel.
    """
    value = binding.value
    data_type = value.data_type
    if binding.id in revision_date_binding_ids(revision) or value.channel in {
        BindingValueChannel.DATE,
        BindingValueChannel.ROW_SET,
    }:
        channel = ModeloEditValueChannel.UNAVAILABLE
        family = ModeloEditValueFamily.DATE if data_type is BindingDataType.DATE else ModeloEditValueFamily.TEXT
    elif binding.id in enum_consumed_binding_ids(revision):
        channel, family = ModeloEditValueChannel.TEXT, ModeloEditValueFamily.TEXT
    elif data_type in _BINDING_DECIMAL_TYPES:
        channel = ModeloEditValueChannel.DECIMAL
        family = {
            BindingDataType.INTEGER: ModeloEditValueFamily.INTEGER,
            BindingDataType.BOOLEAN: ModeloEditValueFamily.BOOLEAN,
        }.get(data_type, ModeloEditValueFamily.DECIMAL)
    else:
        channel, family = ModeloEditValueChannel.UNAVAILABLE, ModeloEditValueFamily.TEXT
    is_money = data_type is BindingDataType.MONEY
    return ModeloEditValueGrammarV1(
        data_type=data_type.value,
        family=family,
        channel=channel,
        max_fraction_digits=(
            MONEY_FRACTION_DIGITS if is_money else 0 if family is ModeloEditValueFamily.INTEGER else None
        ),
        money_operand_bound=is_money,
    )


__all__ = [
    "MONEY_FRACTION_DIGITS",
    "MONEY_OPERAND_MAXIMUM",
    "ModeloEditChoiceV1",
    "ModeloEditRatioUnit",
    "ModeloEditValueChannel",
    "ModeloEditValueFamily",
    "ModeloEditValueGrammarV1",
    "binding_value_grammar",
    "casilla_value_grammar",
]
