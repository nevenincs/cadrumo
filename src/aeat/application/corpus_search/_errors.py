"""Typed errors for the on-host corpus-search grounding surface.

These are plain application-layer exceptions rather than registered
:class:`aeat.core.errors.AeatError` subclasses: registering an
``AeatError`` requires a locale ``message_key`` in all four catalogues,
and the operator-facing translation/envelope mapping is owned by the
W06.P13 MCP tool layer that consumes this surface. The errors carry the
same ``context`` / ``suggestion`` ergonomics as ``AeatError`` so that
consuming layer can project the install hint and structured context onto
the CLI envelope without loss. Promotion to registered ``AeatError``
codes is a follow-up once the P13 tool boundary and the locale
catalogues are settled.
"""

from __future__ import annotations

from collections.abc import Mapping


class CorpusSearchError(Exception):
    """Base error for the corpus-search grounding surface."""

    def __init__(
        self,
        message: str,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.context: dict[str, object] = dict(context or {})
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
    the semantic stack (``model2vec``), which rides the ``aeat[search]``
    extra; when it is absent the surface refuses with an install hint
    (``suggestion``) rather than crashing, and the degraded lexical-only
    mode stays live.
    """


__all__ = [
    "CorpusSearchDependencyError",
    "CorpusSearchError",
    "CorpusSearchInputError",
]
