"""Application-layer :class:`~cadrumo.core.errors.ErrorCode` registry aggregator.

Combines the ordered application shards into the tuple consumed by
:mod:`cadrumo.core.errors.error_codes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._application_part1 import _DECLARED_ERROR_CODES as _APPLICATION_PART1_CODES
from ._application_part2 import _DECLARED_ERROR_CODES as _APPLICATION_PART2_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

_DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *_APPLICATION_PART1_CODES,
    *_APPLICATION_PART2_CODES,
)
