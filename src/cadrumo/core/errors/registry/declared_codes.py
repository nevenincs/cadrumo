"""Layered declarations for the public :class:`core.errors.error_codes.ErrorCode` registry.

Each child module contributes ordered ``(qualname, ErrorCode)`` rows for
one architectural layer. :mod:`core.errors.error_codes` imports the
combined tuple and binds each :class:`core.errors.hierarchy.CadrumoError`
subclass to its declared metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .adapters import DECLARED_ERROR_CODES
from .application import DECLARED_ERROR_CODES as APPLICATION_APPLICATION_CODES
from .client import DECLARED_ERROR_CODES as CLIENT_CLIENT_CODES
from .core import DECLARED_ERROR_CODES as CORE_CORE_CODES
from .domain import DECLARED_ERROR_CODES as DOMAIN_DOMAIN_CODES
from .entrypoints import DECLARED_ERROR_CODES as ENTRYPOINTS_ENTRYPOINTS_CODES

if TYPE_CHECKING:
    from ..error_codes import ErrorCode

ALL_DECLARED_ERROR_CODES: tuple[tuple[str, ErrorCode], ...] = (
    *DOMAIN_DOMAIN_CODES,
    *DECLARED_ERROR_CODES,
    *CLIENT_CLIENT_CODES,
    *ENTRYPOINTS_ENTRYPOINTS_CODES,
    *CORE_CORE_CODES,
    *APPLICATION_APPLICATION_CODES,
)
