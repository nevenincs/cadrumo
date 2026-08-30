"""Typed errors for the on-host corpus-search grounding surface.

These are registered :class:`~core.errors.CadrumoError` subclasses, so a
corpus-search failure that reaches the CLI boundary renders as its proper
category envelope (a ``REFUSED`` input/dependency refusal, an ``ERROR`` base)
rather than collapsing into the generic ``INTERNAL`` unexpected-boundary path.
Each class binds one registered ``ErrorCode`` (declared in
``core.errors.registry._application_part1``) whose ``message_key`` supplies the
localized envelope message, and the specifics ride on ``context`` — the same
contextual detail an external adapter may project onto an envelope (the offending
query/limit/ref). The condition itself travels as a ``reason`` discriminant
rather than as a sentence: a free-form constructor message would be preferred
by ``str(exc)`` over the registered key, so it would reach tracebacks, logs and
every direct rendering of the exception in English regardless of locale.

There is no dependency refusal here: the retrieval surface needs no optional
package, so it can never refuse for want of one.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.errors.hierarchy import CadrumoError


class CorpusSearchError(CadrumoError):
    """Base error for the corpus-search grounding surface."""

    def __init__(
        self,
        *,
        reason: str,
        translated_message: str = "errors.error.error_corpus_search",
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Initialize this public contract."""
        super().__init__(translated_message=translated_message, context={"reason": reason, **dict(context or {})})
        # Preserve the surface's always-a-dict ``context`` contract (CadrumoError's
        # own base leaves it None when unset); consumers read ``.context`` as a
        # mapping.
        self.context = {"reason": reason, **dict(context or {})}
        self.reason = reason


class CorpusSearchInputError(CorpusSearchError):
    """Raised when a corpus-search request cannot be satisfied.

    Covers an unknown citation id, a corpus_ref whose backing extracted
    text is missing, an empty query, and any other caller-supplied input
    the surface refuses. Which of those it is travels as ``reason``.
    """

    def __init__(
        self,
        *,
        reason: str,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Initialize this public contract."""
        super().__init__(
            reason=reason,
            translated_message="errors.refused.refused_corpus_search_input",
            context=context,
        )


__all__ = [
    "CorpusSearchError",
    "CorpusSearchInputError",
]
