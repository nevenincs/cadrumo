"""Wizard error hierarchy.

Every wizard error inherits from :class:`AeatError` so callers can
catch the package-wide base class to handle every aeat domain error
uniformly. Each concrete subclass is bound to an :class:`ErrorCode`
in the application error registry.
"""

from __future__ import annotations

from ...core.errors import AeatError


class WizardError(AeatError):
    """Base class for every wizard error."""


class WizardValidationError(WizardError):
    """Raised when a widget-level validator rejects an answer."""
