"""Errors raised by the Terminology Handbook loader.

These errors are deliberately NOT part of the :class:`cadrumo.core.errors.hierarchy.CadrumoError`
hierarchy. That hierarchy exists for operator-facing runtime failures
that need a registered :class:`~cadrumo.core.errors.error_codes.ErrorCode`, a translated
message, and JSON-envelope redaction at the CLI boundary. The Handbook
loader is build-time documentation tooling: a malformed fragment is a
developer/CI failure surfaced as a stack trace, exactly like the
:exc:`pydantic.ValidationError` it most often wraps. Subclassing
:class:`ValueError` keeps the loader self-contained, lets pydantic treat
schema-rule failures uniformly, and avoids enrolling a build-tooling
error into the runtime error-code registry.
"""

from __future__ import annotations

__all__ = ["TerminologyError", "TerminologyLoadError", "TerminologyValidationError"]


class TerminologyError(ValueError):
    """Base error for every Terminology Handbook failure mode."""


class TerminologyLoadError(TerminologyError):
    """Raised when a Handbook fragment cannot be read or parsed as TOML."""


class TerminologyValidationError(TerminologyError):
    """Raised when a Handbook fragment violates the concept schema.

    Wraps the structural integrity failures the loader checks itself
    (e.g. duplicate ``concept_id`` across fragments, an authored
    ``narrower`` that the loader derives) and re-raises the
    :exc:`pydantic.ValidationError` surface for per-field rule failures.
    """
