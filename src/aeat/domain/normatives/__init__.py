"""Spanish tax normatives corpus subpackage.

Provides a strictly-validated :class:`NormativeCatalogue` of the Spanish tax
normatives the autónomo automation cites. Every :class:`NormativeReference` is a
strict pydantic v2 model, every permalink points at a real BOE consolidated-text
URL, and :func:`~aeat.domain.normatives._verify.verify_catalogue` checks the
committed corpus before use.

Public surface — callers from outside this subpackage must import
exclusively from :mod:`aeat.domain.normatives` and MUST NOT reach into private
``_schema``, ``_loader``, ``_lookup``, ``_cite``, or ``_verify`` modules.

Example::

    >>> from aeat.domain.normatives import NORMATIVE_CATALOGUE, cite, find_articulo
    >>> reference = NORMATIVE_CATALOGUE.get("ley-35-2006")
    >>> if reference is not None:
    ...     art_32 = find_articulo(NORMATIVE_CATALOGUE, "ley-35-2006", "32")
    ...     print(cite(reference, art_32))
"""

from __future__ import annotations

from ._cite import cite, short_title
from ._errors import (
    NormativeError,
    NormativeNotFoundError,
    NormativeParseError,
)
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


class _LazyCatalogue:
    """Module-level singleton that loads ``corpus/normatives/`` on demand.

    The singleton lazily triggers :func:`~aeat.domain.normatives.load_catalogue` on first
    attribute access and caches the result for every subsequent call.
    Tests that need to rebind the corpus root on a per-test basis
    should call :func:`~aeat.domain.normatives.load_catalogue` directly with a settings
    override rather than going through this singleton.
    """

    _cache: NormativeCatalogue | None = None

    def _ensure(self) -> NormativeCatalogue:
        if self._cache is None:
            self._cache = load_catalogue()
        return self._cache

    def reload(self) -> NormativeCatalogue:
        """Force a re-read of the corpus and return the fresh :class:`NormativeCatalogue`."""
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
        """Return the reference keyed by ``ref_id`` or ``None`` if absent.

        Returns:
            The :class:`NormativeReference` for ``ref_id``, or ``None`` when not found.
        """
        return self._ensure().get(ref_id)


NORMATIVE_CATALOGUE = _LazyCatalogue()
"""Lazily-loaded module-level :class:`NormativeCatalogue` singleton.

Triggers :func:`~aeat.domain.normatives.load_catalogue` on first access and caches the result. Tests that
rebind the corpus root per-test should call :func:`~aeat.domain.normatives.load_catalogue` directly.
"""


__all__ = [
    "NORMATIVE_CATALOGUE",
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
