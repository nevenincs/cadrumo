"""Export-exemption-reason schema axis for registry casillas.

Hydrates the TOML token into the closed :class:`~core.ExportExemptionReason`
vocabulary at the registry boundary, so an unknown token is refused at load with
the accepted set named rather than reaching a downstream branch on a raw string.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator

from ....core import ExportExemptionReason
from .errors import RegistryValidationError

__all__ = ["ExportExemptionReasonValue"]


def _coerce_export_exemption_reason(value: object) -> object:
    """Coerce a TOML string literal to the canonical ExportExemptionReason member."""
    if isinstance(value, ExportExemptionReason):
        return value
    if isinstance(value, str):
        try:
            return ExportExemptionReason(value)
        except ValueError:
            raise RegistryValidationError(
                f"export_exemption_reason {value!r} is not a recognised ExportExemptionReason "
                f"member; expected one of {[member.value for member in ExportExemptionReason]}",
            ) from None
    raise RegistryValidationError(
        f"export_exemption_reason must be a string, got {type(value).__name__!r}",
    )


ExportExemptionReasonValue = Annotated[
    ExportExemptionReason,
    BeforeValidator(_coerce_export_exemption_reason),
]
"""Annotated ExportExemptionReason that coerces TOML string literals to enum members."""
