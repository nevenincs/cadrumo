"""Cross-branch dependency stubs for ``aeat.manuals``.

While sibling feature branches ``#17`` (corpus fetcher), ``#21`` (LLM
client + translator), and ``#6`` (modelo identifiers) are still in
flight, this module declares the minimal ``typing.Protocol`` surfaces
and validation constants that ``aeat.manuals`` relies on so the
subpackage can compile, type-check, and test end-to-end today.

Every symbol in this module is explicitly flagged as a stub and is
scheduled for removal in a follow-up PR once the real subpackages
land:

- ``FetcherProtocol`` — replaced by ``aeat.corpus.Fetcher`` (``#17``).
- ``LLMClientProtocol`` / ``TranslatorProtocol`` /
  ``BulkTranslatorProtocol`` — replaced by the real surfaces from
  ``aeat.llm`` (``#21``).
- ``MODELO_CASILLA_PATTERN`` — replaced by a direct cross-reference
  to ``aeat.models.ModeloId`` (``#6``).

Callers import from the ``aeat.manuals`` public surface and MUST NOT
reach into this private module from outside the subpackage.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

# TODO(#6): replace with aeat.models.ModeloId-based validation once #6 lands.
# Pattern matches identifiers of the form ``MODELO_130`` optionally followed by
# a colon and an alphanumeric casilla code, e.g. ``MODELO_130:01``.
MODELO_CASILLA_PATTERN = r"^MODELO_[0-9]{3}(?::[0-9A-Z_]+)?$"


@runtime_checkable
class FetcherProtocol(Protocol):
    """Stub for the ``#17`` ``aeat.corpus.Fetcher`` ABC.

    ``aeat.manuals._fetch`` currently uses ``httpx`` directly; this
    Protocol is the forcing function for the follow-up PR that
    delegates through the real corpus fetcher once ``#17`` merges.
    """

    def fetch(self, url: str, *, dest: Path) -> Path:  # pragma: no cover - stub
        """Download ``url`` to ``dest`` and return the written path."""
        ...


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Stub for the ``#21`` ``aeat.llm.LLMClient`` surface.

    ``aeat.manuals`` uses this protocol to type-annotate the three
    planned-blocker CLI commands (``structure``, ``extract-rules``,
    ``translate``) so their dependency on ``#21`` is visible to
    ``ty`` today.
    """

    def complete(self, prompt: str, *, system: str | None = None) -> str:  # pragma: no cover - stub
        """Run a completion request and return the raw text response."""
        ...


@runtime_checkable
class TranslatorProtocol(Protocol):
    """Stub for the ``#21`` ``aeat.llm.Translator`` surface."""

    def translate(
        self,
        text: str,
        *,
        source: str,
        target: str,
    ) -> str:  # pragma: no cover - stub
        """Translate ``text`` from ``source`` language to ``target``."""
        ...


@runtime_checkable
class BulkTranslatorProtocol(Protocol):
    """Stub for the ``#21`` ``aeat.llm.BulkTranslator`` surface."""

    def translate_many(
        self,
        texts: tuple[str, ...],
        *,
        source: str,
        target: str,
    ) -> tuple[str, ...]:  # pragma: no cover - stub
        """Bulk translate ``texts`` from ``source`` to ``target``."""
        ...


def stub_extracted_at() -> datetime:
    """Return a deterministic UTC datetime placeholder for stub provenance.

    Unused by v1 code but exported so follow-up tests can construct
    synthetic ``LLMProvenance`` records without colliding with the
    real extractor.
    """
    return datetime(2000, 1, 1, 0, 0, 0)
