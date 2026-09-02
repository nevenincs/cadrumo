"""Error hierarchy for the unified review queue.

All review-layer errors inherit from :class:`ReviewError`, which in
turn inherits from :class:`cadrumo.core.errors.CadrumoError` per the
project's package-wide error-base mandate. Callers can therefore catch
either :class:`ReviewError` for review-specific failures or the
package-wide :exc:`cadrumo.core.errors.CadrumoError` to handle every aeat
domain error uniformly.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class ReviewError(CadrumoError):
    """Base class for every error raised by :mod:`cadrumo.application.review`."""


class ReviewSourceLoadError(ReviewError):
    """Raised when a source disk file is present but cannot be parsed."""


class FilterParseError(ReviewError):
    """Raised when ``--filter KEY=VALUE`` cannot be parsed.

    Carries the raw token plus a stable reason code so the CLI can render
    a per-language repair hint.

    Attributes:
        raw_token: The string the operator supplied (e.g. ``"status="`` or
            ``"period: 1T"``). Stored as an internal diagnostic attribute,
            but omitted from rendered messages and context because
            filter values may include free-text search strings or
            imported identifiers.
        safe_token: A redacted token that preserves the key when it is
            parseable and replaces the value with ``<redacted>``.
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
        key = _safe_token_key(raw_token, flag="--filter")
        if key is not None:
            context["key"] = key
        super().__init__(
            context=context,
            translated_message="review.filter.errors.parse_failed",
        )
        self.raw_token = raw_token
        self.safe_token = _safe_token_display(raw_token, flag="--filter")
        self.reason = reason


def _safe_token_key(raw_token: str, *, flag: str) -> str | None:
    """Return a parsed token key without exposing the supplied value."""
    token = raw_token.removeprefix(f"{flag} ").strip()
    key, separator, _value = token.partition("=")
    if not separator:
        return None
    stripped = key.strip().lower()
    return stripped or None


def _safe_token_display(raw_token: str, *, flag: str) -> str:
    """Return a CLI-safe token display that never includes the value."""
    key = _safe_token_key(raw_token, flag=flag)
    if key is None:
        return "<redacted>"
    return f"{key}=<redacted>"


class ReviewKindReservedError(ReviewError):
    """Raised when the CLI receives a reserved kind token.

    Carries the blocking reason returned by
    :func:`cadrumo.application.review.enums.reserved_kind_reason`.

    Attributes:
        token: The ``--kind`` value supplied by the user.
            Stored as an internal diagnostic attribute, but omitted from rendered
            messages and structured context because selector values are
            operator input and may contain copied identifiers.
        reason: Explanation naming the blocking upstream record type.
    """

    def __init__(self, token: str, reason: str) -> None:
        """Construct the error with the offending token and its blocking reason.

        Args:
            token: The ``--kind`` value supplied by the user.
            reason: Human-readable explanation naming the blocking
                upstream record type.
        """
        super().__init__(
            context={"reason": reason},
            translated_message="review.operator.errors.reserved_kind",
        )
        self.token = token
        self.reason = reason
