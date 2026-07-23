"""Flow-substrate error hierarchy.

Every substrate error inherits from :class:`CadrumoError` so callers
catch the package-wide base class to handle every cadrumo domain error
uniformly. The substrate raises typed, translated errors only; raw
operator answers never ride in error context.
"""

from __future__ import annotations

from ...core.errors import CadrumoError, CoreValidationError


class FlowError(CadrumoError):
    """Base class for every flow-substrate error."""


class FlowDefinitionError(FlowError):
    """Raised when a flow definition is structurally invalid at build time."""


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


__all__ = [
    "FlowAnswerError",
    "FlowCheckpointError",
    "FlowCopyResolutionError",
    "FlowDefinitionError",
    "FlowError",
    "FlowNavigationError",
    "FlowSubmitError",
    "FlowValidatorRegistryError",
]
