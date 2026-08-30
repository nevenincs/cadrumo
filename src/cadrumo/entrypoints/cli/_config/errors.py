"""Typed error boundary for the config CLI subpackage.

:exc:`ConfigBoundaryError` wraps unexpected
(non-:class:`CadrumoError`)
exceptions that escape the config command surface so they reach the
structured error-rendering pipeline as a typed envelope rather than being
swallowed or reported as bare Python exceptions.
"""

from __future__ import annotations

from ....core.errors.hierarchy import CoreError


class ConfigBoundaryError(CoreError):
    """Raised when an unexpected exception escapes a config CLI boundary.

    Any exception raised inside a config command that is not already a typed
    :class:`CadrumoError` subclass is wrapped here so downstream
    renderers always receive a typed envelope with a registered
    :class:`ErrorCode`.

    The original exception is preserved on
    :attr:`ConfigBoundaryError.original_exception`
    so tests and log subscribers can inspect the underlying cause without losing
    provenance.

    Attributes:
        original_exception: The underlying exception that triggered the
            boundary wrap.
    """

    def __init__(self, error: Exception) -> None:
        """Wrap ``error`` in the config CLI boundary contract.

        Args:
            error: The unexpected exception raised inside the config
                command handler.
        """
        super().__init__(
            translated_message="errors.error.error_config_boundary",
            context={"error_type": type(error).__name__},
        )
        self.original_exception: Exception = error


__all__ = ["ConfigBoundaryError"]
