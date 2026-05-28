"""Wizard error hierarchy.

Every wizard error inherits from :class:`AeatError` so callers can
catch the package-wide base class to handle every aeat domain error
uniformly. Each concrete subclass is bound to an :class:`ErrorCode`
in the application error registry.
"""

from __future__ import annotations

from ...core.errors import AeatError, CoreValidationError


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


class WizardAnswerTypeError(CoreValidationError):
    """Raised when a :class:`SetupAnswers` field coercion receives an unexpected type.

    Each ``@field_validator`` in :mod:`aeat.application.wizard._setup_answers`
    accepts only the declared union arms (an enum member, a canonical string
    token, or in some cases a blank string).  Any other runtime type violates
    the typed boundary and is rejected with this error instead of a bare
    :class:`TypeError` so the failure propagates through the typed error
    registry and produces a structured envelope.

    Inherits from :class:`CoreValidationError` (which itself inherits from
    :class:`ValueError`) to remain compatible with pydantic's field-validator
    contract while exposing a typed exception in the registry.
    """
