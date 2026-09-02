"""Adapter-layer :class:`~core.errors.ErrorCode` registry aggregator.

Combines the ordered adapter shards into the tuple consumed by
:mod:`core.errors.error_codes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._adapters_part1 import DECLARED_ERROR_CODES as _ADAPTERS_PART1_CODES
from ._adapters_part2 import DECLARED_ERROR_CODES as _ADAPTERS_PART2_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *_ADAPTERS_PART1_CODES,
    *_ADAPTERS_PART2_CODES,
)
