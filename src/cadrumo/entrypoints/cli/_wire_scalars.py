"""Non-decimal JSON-wire scalar types validated against canonical contracts.

Several CLI envelopes are built by dumping a canonical application model to
JSON and re-validating the mapping — for example
``ledger.model_dump(mode="json")`` fed straight into an
:class:`OutputSchema`. That dump renders a ``StrEnum`` as its bare value and a
:class:`datetime.date` as an ISO string, and the strict ``OutputSchema`` base
refuses a bare string for an enum-typed or date-typed field. Declaring those
transport fields as the canonical enum or ``date`` would therefore refuse every
real payload the CLI produces.

These types close the gap from the other side: the field stays a ``str``, so
the passthrough bridge keeps working, while the value is checked against the
same closed set or calendar the canonical model enforces. A transport row can
no longer carry a movement kind or valuation method the domain would reject,
nor a ``movement_date`` that is not a real calendar day.

Decimal magnitudes have the same problem and are handled by the sibling
:mod:`_decimal_wire` module.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator


def enum_value_text(enum_cls: type[StrEnum]) -> object:
    """Return a wire-string type constrained to ``enum_cls``'s accepted values.

    Args:
        enum_cls: The canonical closed set the transport value must belong to.

    Returns:
        An ``Annotated[str, ...]`` type accepting exactly the enum's values.
        The refusal names the accepted set, so a malformed payload reports the
        options rather than a bare "value invalid".
    """
    accepted = tuple(member.value for member in enum_cls)

    def _check(value: str) -> str:
        if value not in accepted:
            raise ValueError(f"{value!r} is not one of the accepted {enum_cls.__name__} values: {', '.join(accepted)}")
        return value

    return Annotated[str, AfterValidator(_check)]


def _validate_iso_date(value: str) -> str:
    """Return ``value`` when it is a real ISO-8601 calendar day."""
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"{value!r} is not an ISO-8601 calendar date; the accepted form is zero-padded YYYY-MM-DD"
        ) from None
    return value


IsoDateText = Annotated[str, AfterValidator(_validate_iso_date)]
"""A calendar day rendered for the JSON wire as a zero-padded ISO-8601 string."""

__all__ = ["IsoDateText", "enum_value_text"]
