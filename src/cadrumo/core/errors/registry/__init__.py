"""Layered declarations for the public :class:`core.errors.ErrorCode` registry.

Each child module contributes ordered ``(qualname, ErrorCode)`` rows for
one architectural layer. :mod:`core.errors.error_codes` imports the
combined tuple and binds each :class:`core.errors.CadrumoError`
subclass to its declared metadata.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
