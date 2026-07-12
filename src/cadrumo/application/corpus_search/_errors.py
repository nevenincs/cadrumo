"""Typed errors for the on-host corpus-search grounding surface.

These are registered :class:`~core.errors.AeatError` subclasses, so a
corpus-search failure that reaches the CLI boundary renders as its proper
category envelope (a ``REFUSED`` input/dependency refusal, an ``ERROR`` base)
rather than collapsing into the generic ``INTERNAL`` unexpected-boundary path.
Each class binds one registered ``ErrorCode`` (declared in
``core.errors.registry._application_part1``) whose ``message_key`` supplies the
localized envelope message; the free-form constructor ``message`` stays as the
developer-facing ``str(exc)`` detail and the specifics ride on ``context`` — the
same ``context`` / ``suggestion`` ergonomics the MCP tool layer already projects
onto the envelope (the install hint, the offending query/limit/ref).
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.errors import AeatError


class CorpusSearchError(AeatError):
    """Base error for the corpus-search grounding surface."""

    def __init__(
        self,
        message: str,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        # Preserve the surface's always-a-dict ``context`` contract (AeatError's
        # own base leaves it None when unset); consumers read ``.context`` as a
        # mapping.
        self.context = dict(context or {})
        self.suggestion = suggestion


class CorpusSearchInputError(CorpusSearchError):
    """Raised when a corpus-search request cannot be satisfied.

    Covers an unknown citation id, a corpus_ref whose backing extracted
    text is missing, an empty query, and any other caller-supplied input
    the surface refuses.
    """


class CorpusSearchDependencyError(CorpusSearchError):
    """Raised when an operation needs the capability-gated ``search`` extra.

    The lexical index and the citation lookup run on the standard library
    plus ``snowballstemmer`` and are always importable. Only the
    build-time embedding precompute and the runtime query embedder need
    the semantic stack (``model2vec``), which rides the ``aeat-cli[search]``
    extra; when it is absent the surface refuses with an install hint
    (``suggestion``) rather than crashing, and the degraded lexical-only
    mode stays live.
    """


__all__ = [
    "CorpusSearchDependencyError",
    "CorpusSearchError",
    "CorpusSearchInputError",
]
