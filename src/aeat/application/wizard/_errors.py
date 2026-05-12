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


class WizardScriptUnderflowError(WizardError):
    """Raised when a ``ScriptedPrompter`` is asked for more answers than it carries."""


class WizardScriptOverflowError(WizardError):
    """Raised when a ``ScriptedPrompter`` is closed with unconsumed scripted answers."""


class WizardMissingFlagError(WizardError):
    """Raised when a ``--quiet`` invocation omits a required-and-not-conditional question."""


class WizardCompileError(WizardError):
    """Raised when ``compile_profile_keys`` rejects a malformed wizard catalogue."""
