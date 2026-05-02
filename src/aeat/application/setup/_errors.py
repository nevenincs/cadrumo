"""Domain errors raised by the first-run setup wizard.

Every setup-wizard error inherits from
:class:`aeat.core.errors.AeatError` so callers can catch the
package-wide base class to handle every aeat domain error uniformly.
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
