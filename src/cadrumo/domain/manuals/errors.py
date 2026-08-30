"""Domain errors for the :mod:`cadrumo.domain.manuals` subpackage.

Every exception raised by loading, verifying, fetching, or extracting
from the AEAT *Manual práctico* corpus inherits from
:class:`ManualError`, which in turn inherits from
:class:`cadrumo.core.errors.CadrumoError`.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class ManualError(CadrumoError):
    """Base error for every :mod:`cadrumo.domain.manuals` failure mode."""


class ManualNotFoundError(ManualError):
    """Raised when a requested manual/year/part is missing on disk."""


class ManualParseError(ManualError):
    """Raised when a committed manual record fails schema validation."""


class ManualReviewRequiredError(ManualError):
    """Raised when a persisted record lacks reviewer metadata.

    The verify CLI rejects any :class:`~cadrumo.domain.manuals.Manual`,
    :class:`~cadrumo.domain.manuals.Section`, or
    :class:`~cadrumo.domain.manuals.Rule` record missing
    ``definition_reviewed_by`` or ``definition_reviewed_at`` when the
    ``CADRUMO_MANUALS_REVIEW_REQUIRED`` setting is enabled.
    """


class RuleExtractionError(ManualError):
    """Raised by LLM-dependent CLI subcommands that have no backing implementation.

    The ``structure``, ``extract-rules``, and ``translate`` subcommands
    define their public CLI shape but raise this exception until the
    :mod:`cadrumo.adapters.outbound.llm` subpackage is available.
    """


class ManifestError(ManualError):
    """Raised when a ``manifest.json`` fails schema or sha256 checks."""


class ManualValidationError(ManualError, ValueError):
    """Raised when manual records violate state or shape invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """


__all__ = [
    "ManifestError",
    "ManualError",
    "ManualNotFoundError",
    "ManualParseError",
    "ManualReviewRequiredError",
    "ManualValidationError",
    "RuleExtractionError",
]
