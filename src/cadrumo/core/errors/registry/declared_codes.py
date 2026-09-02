"""Layered declarations for the public :class:`core.errors.ErrorCode` registry.

Each child module contributes ordered ``(qualname, ErrorCode)`` rows for
one architectural layer. :mod:`core.errors.error_codes` imports the
combined tuple and binds each :class:`core.errors.CadrumoError`
subclass to its declared metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._adapters import DECLARED_ERROR_CODES as _ADAPTERS_CODES
from ._application import DECLARED_ERROR_CODES as _APPLICATION_CODES
from ._core import DECLARED_ERROR_CODES as _CORE_CODES
from ._domain import DECLARED_ERROR_CODES as _DOMAIN_CODES
from ._entrypoints import DECLARED_ERROR_CODES as _ENTRYPOINTS_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

ALL_DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *_DOMAIN_CODES,
    *_ADAPTERS_CODES,
    *_ENTRYPOINTS_CODES,
    *_CORE_CODES,
    *_APPLICATION_CODES,
)
