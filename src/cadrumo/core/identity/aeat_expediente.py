"""Canonical AEAT expediente identifier and its validated shape."""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import StringConstraints

__all__ = [
    "AEAT_EXPEDIENTE_ID_MAX_LENGTH",
    "AEAT_EXPEDIENTE_ID_MIN_LENGTH",
    "AEAT_EXPEDIENTE_ID_PATTERN",
    "AeatExpedienteId",
]


AEAT_EXPEDIENTE_ID_MIN_LENGTH: Final[int] = 12
AEAT_EXPEDIENTE_ID_MAX_LENGTH: Final[int] = 32
AEAT_EXPEDIENTE_ID_PATTERN: Final[str] = r"^[0-9]{4,}[A-Z0-9]+$"


AeatExpedienteId = Annotated[
    str,
    StringConstraints(
        min_length=AEAT_EXPEDIENTE_ID_MIN_LENGTH,
        max_length=AEAT_EXPEDIENTE_ID_MAX_LENGTH,
        pattern=AEAT_EXPEDIENTE_ID_PATTERN,
    ),
]
"""An AEAT expediente id at the observed 12-32 character contract."""
