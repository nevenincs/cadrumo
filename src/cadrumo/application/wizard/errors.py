"""Wizard error hierarchy.

Every wizard error inherits from :class:`CadrumoError` so callers can
catch the package-wide base class to handle every cadrumo domain error
uniformly. Each concrete subclass is bound to an :class:`ErrorCode`
in the application error registry.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from ...core.errors.hierarchy import (
    CadrumoError,
    CoreValidationError,
    ProfileAnswerTypeError,
    TerminalPreconditionErrorMixin,
)
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions._models import PreconditionVerdict
from ..operator_actions._preconditions import no_action_precondition_verdict


class WizardPreconditionCondition(StrEnum):
    """Stable terminal conditions observed by the wizard boundary."""

    ACTIVE_PROFILE_AVAILABLE = "wizard.active_profile.available"
    ACTIVE_PROFILE_TAX_ID_DECLARED = "wizard.active_profile.tax_id.declared"
    FILING_BASELINE_COMPLETE = "wizard.filing_baseline.complete"
    REQUIRED_FLAGS_SUPPLIED = "wizard.required_flags.supplied"
    PROFILE_NAME_SUPPLIED = "wizard.profile_name.supplied"
    PROFILE_LABEL_AVAILABLE = "wizard.profile_label.available"
    INTERACTIVE_CONSOLE_AVAILABLE = "wizard.interactive_console.available"


def wizard_no_action_verdict(
    *,
    condition: WizardPreconditionCondition,
    facts: Mapping[str, str | int | bool],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
):
    """Delegate one fact-only wizard terminal refusal to the public authority."""
    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=provenance,
        outcome=outcome,
    )


class WizardError(TerminalPreconditionErrorMixin[PreconditionVerdict], CadrumoError):
    """Base class for every wizard error."""


class WizardValidationError(WizardError, CoreValidationError):
    """Raised when a widget-level validator rejects an answer.

    Inherits from CoreValidationError (which itself inherits from CoreError
    and ValueError) to participate in the shared CoreValidationError catch
    surface and remain compatible with pydantic field validators.
    """


class WizardUnsupportedConsoleError(WizardError):
    """Raised when the host terminal cannot host the interactive setup wizard.

    Raised at the CLI boundary wrapping the flow substrate's console refusal.
    The terminal verdict records only the failed console capability; it does
    not invent a follow-on command from a host limitation.
    """


class WizardEditUnsupportedConsoleError(WizardUnsupportedConsoleError):
    """No-console refusal raised specifically from the ``profile edit`` flow.

    This subclass keeps the edit-specific registered error code while sharing
    the same factual terminal console-capability outcome as the base error.
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


__all__ = [
    "WizardAnswerTypeError",
    "WizardCompileError",
    "WizardEditUnsupportedConsoleError",
    "WizardError",
    "WizardMissingFlagError",
    "WizardPreconditionCondition",
    "WizardUnsupportedConsoleError",
    "WizardValidationError",
    "wizard_no_action_verdict",
]
