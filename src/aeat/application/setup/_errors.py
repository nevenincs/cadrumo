"""Domain errors for the first-run setup wizard (#61).

Every setup-wizard error inherits from :class:`aeat.errors.AeatError`
so callers can catch the package-wide base class.
"""

from __future__ import annotations

from ...core.errors import AeatError


class SetupError(AeatError):
    """Base class for every setup-wizard error."""


class SetupAbortedError(SetupError):
    """Raised when the user explicitly aborts the wizard."""


class SetupVerifyError(SetupError):
    """Raised when the verify step finds an ERROR-severity problem."""


class SetupAnswersError(SetupError):
    """Raised when a :class:`SetupAnswers` payload cannot be loaded or validated."""
