"""Wizard error hierarchy.

Every wizard error inherits from :class:`CadrumoError` so callers can
catch the package-wide base class to handle every cadrumo domain error
uniformly. Each concrete subclass is bound to an :class:`ErrorCode`
in the application error registry.
"""

from __future__ import annotations

from ...core.errors import CadrumoError, CoreValidationError, ProfileAnswerTypeError


class WizardError(CadrumoError):
    """Base class for every wizard error."""


class WizardValidationError(WizardError, CoreValidationError):
    """Raised when a widget-level validator rejects an answer.

    Inherits from CoreValidationError (which itself inherits from CoreError
    and ValueError) to participate in the shared CoreValidationError catch
    surface and remain compatible with pydantic field validators.
    """


class WizardUnsupportedConsoleError(WizardError):
    """Raised when the host terminal cannot host the interactive setup wizard.

    Raised at the CLI boundary wrapping the flow substrate's console
    refusal: the wizard-branded class carries the setup-specific
    recovery suggestion (the non-interactive ``profile create`` flag
    form) that the substrate's generic refusal cannot know about.
    """


class WizardEditUnsupportedConsoleError(WizardUnsupportedConsoleError):
    """No-console refusal raised specifically from the ``profile edit`` flow.

    The base error's recovery suggestion names ``profile create``, which
    reads as a destructive replacement when an operator hit the
    no-console state via ``profile edit``. This subclass carries its own
    registered error code so the trailing recovery suggestion names the
    non-interactive ``profile edit`` patch form instead.
    """


class WizardMissingFlagError(WizardError):
    """Raised when a ``--quiet`` invocation omits a required-and-not-conditional question."""


class WizardCompileError(WizardError):
    """Raised when ``compile_profile_keys`` rejects a malformed wizard catalogue."""


class WizardAnswerTypeError(ProfileAnswerTypeError):
    """Raised when a :class:`SetupAnswers` field coercion receives an unexpected type.

    Each ``@field_validator`` in :mod:`cadrumo.core.setup_answers`'s :class:`SetupAnswers`
    raises :class:`~cadrumo.core.errors.ProfileAnswerTypeError` (the canonical core
    type); this subclass is retained so application-layer code and tests that
    catch :class:`WizardAnswerTypeError` by name continue to work.

    Inherits from :class:`~cadrumo.core.errors.ProfileAnswerTypeError` (which inherits
    from :class:`CoreValidationError` and :class:`ValueError`) to remain compatible
    with pydantic's field-validator contract while exposing a typed exception in
    the error registry.
    """
