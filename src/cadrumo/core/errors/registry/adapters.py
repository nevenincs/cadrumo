"""Adapter-layer :class:`~core.errors.error_codes.ErrorCode` registry aggregator.

Combines the inbound, outbound and persistence adapter registrations into the
tuple consumed by :mod:`core.errors.error_codes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .adapters_inbound import DECLARED_ERROR_CODES as ADAPTERS_INBOUND_INBOUND_CODES
from .adapters_outbound import DECLARED_ERROR_CODES as ADAPTERS_OUTBOUND_OUTBOUND_CODES
from .adapters_persistence import DECLARED_ERROR_CODES as ADAPTERS_PERSISTENCE_PERSISTENCE_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *ADAPTERS_INBOUND_INBOUND_CODES,
    *ADAPTERS_OUTBOUND_OUTBOUND_CODES,
    *ADAPTERS_PERSISTENCE_PERSISTENCE_CODES,
)
