"""Spanish tax normatives corpus subpackage.

Provides a strictly-validated catalogue of the Spanish tax normatives
the autónomo automation cites. Every record is a strict pydantic v2
model. Every permalink points at a real BOE consolidated-text URL.
Every committed file is hand-reviewed before it lands on ``main``.

Public surface — callers from outside this subpackage must import
exclusively from ``aeat.domain.normatives`` and MUST NOT reach into private
``_schema``, ``_loader``, ``_lookup``, ``_cite``, or ``_verify``
modules.

Example::

    >>> from aeat.domain.normatives import NORMATIVE_CATALOGUE, cite, find_articulo
    >>> reference = NORMATIVE_CATALOGUE.get("ley-35-2006")
    >>> if reference is not None:
    ...     art_32 = find_articulo(NORMATIVE_CATALOGUE, "ley-35-2006", "32")
    ...     print(cite(reference, art_32))
"""

from __future__ import annotations

from ._cite import cite, short_title
from ._loader import load_catalogue
from ._lookup import find_articulo, find_reference
from ._schema import (
    Articulo,
    NormativeCatalogue,
    NormativeKind,
    NormativeReference,
    NormativeVerificationIssue,
    NormativeVerificationReport,
)
from ._verify import raise_on_errors, verify_catalogue
from .errors import (
    NormativeError,
    NormativeNotFoundError,
    NormativeParseError,
)


class _LazyCatalogue:
    """Module-level singleton that loads ``corpus/normatives/`` on demand.

    The singleton lazily triggers :func:`load_catalogue` on first
    attribute access and caches the result for every subsequent call.
    Tests that need to rebind the corpus root on a per-test basis
    should call :func:`load_catalogue` directly with a settings
    override rather than going through this singleton.
    """

    _cache: NormativeCatalogue | None = None

    def _ensure(self) -> NormativeCatalogue:
        if self._cache is None:
            self._cache = load_catalogue()
        return self._cache

    def reload(self) -> NormativeCatalogue:
        """Force a re-read of the corpus and return the fresh catalogue."""
        self._cache = load_catalogue()
        return self._cache

    def __getattr__(self, name: str) -> object:
        return getattr(self._ensure(), name)

    def __iter__(self):
        return iter(self._ensure())

    def __len__(self) -> int:
        return len(self._ensure())

    def __contains__(self, key: object) -> bool:
        return key in self._ensure()

    def get(self, ref_id: str) -> NormativeReference | None:
        """Return the reference keyed by ``ref_id`` or ``None`` if absent."""
        return self._ensure().get(ref_id)


__all__ = [
    "Articulo",
    "NormativeCatalogue",
    "NormativeError",
    "NormativeKind",
    "NormativeNotFoundError",
    "NormativeParseError",
    "NormativeReference",
    "NormativeVerificationIssue",
    "NormativeVerificationReport",
    "cite",
    "find_articulo",
    "find_reference",
    "load_catalogue",
    "raise_on_errors",
    "short_title",
    "verify_catalogue",
]
