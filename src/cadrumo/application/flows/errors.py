"""Canonical flow-substrate error hierarchy.

Every substrate error inherits from :class:`CadrumoError` so callers
catch the package-wide base class to handle every cadrumo domain error
uniformly. The substrate raises typed, translated errors only; raw
operator answers never ride in error context.
"""

from __future__ import annotations

from ...core.errors import CadrumoError, CoreValidationError


class FlowError(CadrumoError):
    """Base class for every flow-substrate error."""


class FlowValidatorRegistryError(FlowError):
    """Raised on a blank, duplicate, or unknown validator-id registration or lookup."""


class FlowNavigationError(FlowError):
    """Raised when a navigation intent names a page the current state cannot reach."""


class FlowAnswerError(FlowError, CoreValidationError):
    """Raised when an answer intent targets a page that cannot accept it.

    Inherits from :class:`CoreValidationError` to participate in the
    shared validation catch surface.
    """


class FlowSubmitError(FlowError):
    """Raised when submission is attempted while the review gate refuses it."""


class FlowCheckpointError(FlowError):
    """Raised when a checkpoint or resume operation cannot complete."""


class FlowCopyResolutionError(FlowError):
    """Raised when a copy reference cannot be resolved against its declared source."""


class FlowRunAbandonedError(FlowError):
    """Raised when the operator abandons a line-mode prompt loop (Ctrl-C).

    The line frontend prompts through ``unsafe_ask`` so a ``KeyboardInterrupt``
    surfaces at the frontend boundary as a typed, translated refusal instead
    of being swallowed into a silent re-prompt with no cancel path. Context
    carries flow metadata only — never a raw operator answer.
    """


class FlowUnsupportedConsoleError(FlowError):
    """Raised when the host terminal cannot host an interactive flow frontend.

    Surfaces when ``prompt_toolkit`` rejects the active TTY (typically
    ``NoConsoleScreenBufferError`` under git-bash on Windows) or stdin is
    not a TTY. Frontends catch this at their boundary and surface a
    translated operator-facing refusal, never a raw traceback.
    """


__all__ = [
    "FlowAnswerError",
    "FlowCheckpointError",
    "FlowCopyResolutionError",
    "FlowError",
    "FlowNavigationError",
    "FlowRunAbandonedError",
    "FlowSubmitError",
    "FlowUnsupportedConsoleError",
    "FlowValidatorRegistryError",
]
