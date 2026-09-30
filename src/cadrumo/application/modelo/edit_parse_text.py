"""Say why an entry could not be read, as one sentence that tells the filer how to fix it.

The parser refuses with a closed reason and positional arguments -- a bound, a
number of decimals, a length -- and never the refused text itself. This module
names those arguments for the reason's sentence and writes a bound in the
filer's number format, so "above maximum 99999999999.99" reads as "The largest
value allowed is 99.999.999.999,99." in Spanish.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from .edit_models import ModeloEditParseReason, ModeloEditParseRefusalV1
from .value_presentation import SCREEN_MINUS_SIGN, group_decimal_text

_ARGUMENT_NAMES: Final[Mapping[ModeloEditParseReason, tuple[str, ...]]] = MappingProxyType(
    {
        ModeloEditParseReason.TOO_MANY_DECIMALS: ("digits",),
        ModeloEditParseReason.BELOW_MINIMUM: ("bound",),
        ModeloEditParseReason.ABOVE_MAXIMUM: ("bound",),
        ModeloEditParseReason.OUT_OF_OPERAND_RANGE: ("bound",),
        ModeloEditParseReason.NOT_IN_CHOICES: ("count",),
        ModeloEditParseReason.TOO_SHORT: ("length",),
        ModeloEditParseReason.TOO_LONG: ("length",),
    }
)
"""The name of each positional argument a reason's sentence reads; a reason absent here reads none."""


def parse_refusal_text(refusal: ModeloEditParseRefusalV1, language: OutputLanguage) -> str:
    """Return the sentence saying why one entry could not be read, in ``language``."""
    values: dict[str, str] = {}
    for name, argument in zip(_ARGUMENT_NAMES.get(refusal.reason, ()), refusal.message_arguments, strict=False):
        if name == "bound":
            values[name] = group_decimal_text(argument, language, minus=SCREEN_MINUS_SIGN) or argument
        else:
            values[name] = argument
    return tr(f"application.modelo.edit.parse.{refusal.reason.value}", locale=language.value, **values)


__all__ = ["parse_refusal_text"]
