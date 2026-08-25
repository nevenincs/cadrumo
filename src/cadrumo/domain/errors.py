"""Lightweight validation error base for root domain value objects.

Defines :class:`DomainValidationError`, the :class:`core.errors.CadrumoError`
subclass that also behaves as :exc:`ValueError` so Pydantic validators can
surface invalid domain identifiers and models as validation failures.

This module is not a catch-all domain error hierarchy. Focused domain packages
own their package-specific error trees and register those classes with
the central error registry. The root validation base exists for lightweight
cross-domain primitives such as :class:`domain.ModeloIdentifier`, where
importing a larger package-specific authority would be the wrong dependency.
"""

from __future__ import annotations

from ..core.errors import CadrumoError


class DomainValidationError(CadrumoError, ValueError):
    """Raised when root-level domain identifiers or value objects are invalid."""
