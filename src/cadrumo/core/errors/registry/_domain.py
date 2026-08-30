"""Domain-layer :class:`~cadrumo.core.errors.ErrorCode` registry aggregator.

Combines the ordered domain shards into the tuple consumed by
:mod:`cadrumo.core.errors.error_codes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._domain_part1 import _DECLARED_ERROR_CODES as _DOMAIN_PART1_CODES
from ._domain_part2 import _DECLARED_ERROR_CODES as _DOMAIN_PART2_CODES
from ._domain_part3 import _DECLARED_ERROR_CODES as _DOMAIN_PART3_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

_DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *_DOMAIN_PART1_CODES,
    *_DOMAIN_PART2_CODES,
    *_DOMAIN_PART3_CODES,
)
