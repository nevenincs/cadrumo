"""Error hierarchy for the unified review queue.

All review-layer errors inherit from :class:`ReviewError`, which in
turn inherits from :class:`aeat.core.errors.AeatError` per the
project's package-wide error-base mandate. Callers can therefore catch
either :class:`ReviewError` for review-specific failures or the
package-wide :exc:`aeat.core.errors.AeatError` to handle every aeat
domain error uniformly.
"""

from __future__ import annotations

from ...core.errors import AeatError


class ReviewError(AeatError):
    """Base class for every error raised by :mod:`aeat.application.review`."""


class ReviewSourceLoadError(ReviewError):
    """Raised when a source disk file is present but cannot be parsed."""


class FilterParseError(ReviewError):
    """Raised when ``--filter KEY=VALUE`` cannot be parsed.

    Carries the raw token plus a stable reason code so the CLI can render
    a per-language repair hint.

    Attributes:
        raw_token: The string the operator supplied (e.g. ``"status="`` or
            ``"period: 2026-Q1"``).
        reason: One of ``"missing-equals"``, ``"empty-key"``,
            ``"empty-value"``, ``"unknown-key-{scope}"``,
            ``"invalid-value-{scope}"``, ``"duplicate-key-{scope}"``.
    """

    def __init__(self, raw_token: str, *, reason: str) -> None:
        """Construct the error with the offending token and stable reason code.

        Args:
            raw_token: The string the operator supplied.
            reason: Stable reason code (e.g. ``"missing-equals"``,
                ``"empty-key"``, ``"invalid-value-{scope}"``).
        """
        super().__init__(f"cannot parse filter token {raw_token!r}: {reason}")
        self.raw_token = raw_token
        self.reason = reason


class EditParseError(ReviewError):
    """Raised when ``--set KEY=VALUE`` cannot be parsed.

    Attributes:
        raw_token: The string the operator supplied. Kept for callers
            that need to build a CLI recovery hint, but intentionally
            omitted from the rendered error text and structured context
            because edit values may contain file paths, references, or
            operator notes.
        reason: One of ``"missing-equals"``, ``"empty-key"``,
            ``"empty-value"``, ``"unknown-key-{scope}"``,
            ``"invalid-value-{scope}"``, ``"duplicate-key-{scope}"``.
    """

    def __init__(self, raw_token: str, *, reason: str) -> None:
        """Construct the error with the offending token and stable reason code.

        Args:
            raw_token: The string the operator supplied.
            reason: Stable reason code (e.g. ``"missing-equals"``,
                ``"empty-key"``, ``"invalid-value-{scope}"``).
        """
        context: dict[str, object] = {"reason": reason}
        key = _safe_edit_token_key(raw_token)
        if key is not None:
            context["key"] = key
        super().__init__(
            f"cannot parse edit token: {reason}",
            context=context,
            translated_message="review.edit.errors.parse_failed",
        )
        self.raw_token = raw_token
        self.reason = reason


def _safe_edit_token_key(raw_token: str) -> str | None:
    """Return the edit key without exposing the user-supplied value."""
    token = raw_token.removeprefix("--set ").strip()
    key, separator, _value = token.partition("=")
    if not separator:
        return None
    stripped = key.strip().lower()
    return stripped or None


class ReviewKindReservedError(ReviewError):
    """Raised when the CLI receives a reserved kind token.

    Carries the blocking reason returned by
    :func:`aeat.application.review._enums.reserved_kind_reason`.

    Attributes:
        token: The ``--kind`` value supplied by the user.
        reason: Human-readable explanation naming the blocking upstream
            record type.
    """

    def __init__(self, token: str, reason: str) -> None:
        """Construct the error with the offending token and its blocking reason.

        Args:
            token: The ``--kind`` value supplied by the user.
            reason: Human-readable explanation naming the blocking
                upstream record type.
        """
        super().__init__(f"--kind {token!r} is reserved and is not an emitted review kind: {reason}")
        self.token = token
        self.reason = reason
