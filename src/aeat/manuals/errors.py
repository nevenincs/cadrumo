"""Domain errors for the ``aeat.manuals`` subpackage.

All exceptions raised by loading, verifying, fetching, or extracting
from the AEAT *Manual práctico* corpus inherit from :class:`ManualError`
which in turn inherits from :class:`aeat.errors.AeatError`.
"""

from __future__ import annotations

from aeat.errors import AeatError


class ManualError(AeatError):
    """Base error for every ``aeat.manuals`` failure mode."""


class ManualNotFoundError(ManualError):
    """Raised when a requested manual/year/part is missing on disk."""


class ManualParseError(ManualError):
    """Raised when a committed manual record fails schema validation."""


class ManualReviewRequiredError(ManualError):
    """Raised when a persisted record lacks reviewer metadata.

    The verify CLI rejects any ``Manual`` / ``Section`` / ``Rule``
    record missing ``reviewed_by`` or ``reviewed_at`` when the
    ``AEAT_MANUALS_REVIEW_REQUIRED`` setting is enabled.
    """


class RuleExtractionError(ManualError):
    """Raised by the LLM-dependent CLI phases until ``#21`` lands.

    The ``structure``, ``extract-rules``, and ``translate`` subcommands
    are defined in v1 to lock the public CLI shape but raise this
    exception until the ``aeat.llm`` subpackage is available.
    """


class ManifestError(ManualError):
    """Raised when a ``manifest.json`` fails schema or sha256 checks."""
