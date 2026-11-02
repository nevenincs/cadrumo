"""Adapter-layer :class:`~core.errors.error_codes.ErrorCode` registry aggregator.

Combines the inbound, outbound and persistence adapter registrations into the
tuple consumed by :mod:`core.errors.error_codes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._adapters_inbound import DECLARED_ERROR_CODES as _INBOUND_CODES
from ._adapters_outbound import DECLARED_ERROR_CODES as _OUTBOUND_CODES
from ._adapters_persistence import DECLARED_ERROR_CODES as _PERSISTENCE_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *_INBOUND_CODES,
    *_OUTBOUND_CODES,
    *_PERSISTENCE_CODES,
)
