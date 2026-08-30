"""Selector model and build-time validator for the ``design_constant`` family.

A record-design constant is a byte run whose value is fixed by AEAT's own
diseño de registro rather than supplied by the taxpayer: the record-type marker,
the modelo number, a sheet discriminator. The diseño states them in its own
field text -- "Constante número '1'.", "Constante «720»." -- and they are the
same for every filing of that record.

Before this family such a run had no honest home. Routing it through
``manual_input`` asked the operator to type AEAT's record format, and because
that prompt is answerable-blank the run could emit blanks behind a valid digest,
producing a file AEAT cannot parse. Routing it through an inline export literal
was the other candidate and is refused for Modelo 720 by a deliberate contract:
that layout represents every casilla through a binding and pins inline fields to
carry neither a casilla id nor a literal.

So the constant stays a binding and carries its own value. The evidence for the
value is NOT re-declared here: the binding's existing ``source_refs`` already
cites the diseño the constant is read from, which is what a reviewer follows.

What this family is NOT for, and the distinction is load-bearing. A run whose
diseño text offers a blank alternative -- Modelo 369's ``[blanco | constante
"C"]`` -- is CONDITIONAL, and pinning one branch of it here would corrupt the
record. A run whose constant IS blank -- Modelo 714's "Constante. Blanco" -- is
already correctly a filler and gains nothing from a value it does not have. Only
an unconditional constant with a real value belongs here.

See Also:
    :class:`~cadrumo.core.aggregation.BindingSourceKind`
        The canonical closed taxonomy this family's token is a member of.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

from ....core.models import STRICT_FROZEN_CONFIG
from .binding_selector_utils import selector_against_model
from .errors import RegistryValidationError
from .manual_input_selector import ManualInputDataType

if TYPE_CHECKING:
    from .schema import DataBindingDefinition

__all__ = [
    "DESIGN_CONSTANT_RECORD_SHAPE_KEYS",
    "DesignConstantSelector",
    "validate_design_constant_binding",
]

#: The record-field coordinate keys a design constant must declare. Mirrors the
#: manual_input record shape deliberately: the constant occupies a byte run in
#: exactly the same coordinate space, and a second spelling of the same shape
#: would be a place for the two to drift.
DESIGN_CONSTANT_RECORD_SHAPE_KEYS: frozenset[str] = frozenset(("record", "field", "offset", "length"))


class DesignConstantSelector(BaseModel):
    """Strict validator for a ``design_constant`` binding's selector mapping.

    Declares the record-field coordinate plus the literal ``value`` AEAT fixes
    there. The value is a typed field on this model rather than a free-form
    mapping entry, so a malformed constant is a named build-time failure instead
    of a blank at filing time.
    """

    model_config = STRICT_FROZEN_CONFIG

    record: str = Field(min_length=1, max_length=64)
    field: str = Field(min_length=1, max_length=128)
    offset: int = Field(ge=1)
    length: int = Field(ge=1)
    #: How the run is encoded on the wire. Reuses the manual-input vocabulary
    #: rather than declaring a second one: the byte run is the same slot whether
    #: the value arrives from the operator or from the diseño, and a private
    #: spelling here would be a place for the two to disagree about padding.
    data_type: ManualInputDataType
    #: The exact characters AEAT fixes at this run. Compared against ``length``
    #: below, because a constant that does not fill its declared run is a
    #: mis-transcription of the diseño rather than a value to pad silently.
    value: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _validate_value_fills_the_declared_run(self) -> DesignConstantSelector:
        if len(self.value) != self.length:
            raise RegistryValidationError(
                f"design_constant selector value {self.value!r} is {len(self.value)} character(s) "
                f"but the declared run at offset {self.offset} is {self.length}; a constant must "
                "fill its run exactly, because padding one silently is how a mis-read diseño "
                "reaches the wire",
            )
        return self


def validate_design_constant_binding(binding: DataBindingDefinition) -> list[str]:
    """Return every build-time diagnostic for a ``design_constant`` binding.

    Accumulating and never raising, per the one-validator-per-family contract:
    the registry-build section validator collects diagnostics across all
    families, so a raise here would hide every later binding's problems behind
    the first one.
    """
    return selector_against_model(binding, DesignConstantSelector)
