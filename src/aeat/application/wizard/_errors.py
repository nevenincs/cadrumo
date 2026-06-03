"""Wizard error hierarchy.

Every wizard error inherits from :class:`AeatError` so callers can
catch the package-wide base class to handle every aeat domain error
uniformly. Each concrete subclass is bound to an :class:`ErrorCode`
in the application error registry.
"""

from __future__ import annotations

from ...core.errors import AeatError, CoreValidationError, ProfileAnswerTypeError


class WizardError(AeatError):
    """Base class for every wizard error."""


class WizardValidationError(WizardError, CoreValidationError):
    """Raised when a widget-level validator rejects an answer.

    Inherits from CoreValidationError (which itself inherits from CoreError
    and ValueError) to participate in the shared CoreValidationError catch
    surface and remain compatible with pydantic field validators.
    """


class WizardScriptUnderflowError(WizardError):
    """Raised when a ``ScriptedPrompter`` is asked for more answers than it carries."""


class WizardScriptOverflowError(WizardError):
    """Raised when a ``ScriptedPrompter`` is closed with unconsumed scripted answers."""


class WizardMissingFlagError(WizardError):
    """Raised when a ``--quiet`` invocation omits a required-and-not-conditional question."""


class WizardCompileError(WizardError):
    """Raised when ``compile_profile_keys`` rejects a malformed wizard catalogue."""


class WizardAnswerTypeError(ProfileAnswerTypeError):
    """Raised when a :class:`SetupAnswers` field coercion receives an unexpected type.

    Each ``@field_validator`` in :mod:`aeat.core.setup_answers`'s :class:`SetupAnswers`
    raises :class:`~aeat.core.errors.ProfileAnswerTypeError` (the canonical core
    type); this subclass is retained so application-layer code and tests that
    catch :class:`WizardAnswerTypeError` by name continue to work.

    Inherits from :class:`~aeat.core.errors.ProfileAnswerTypeError` (which inherits
    from :class:`CoreValidationError` and :class:`ValueError`) to remain compatible
    with pydantic's field-validator contract while exposing a typed exception in
    the error registry.
    """
