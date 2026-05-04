"""Legacy abstract base for declaración extractors.

The concrete per-model extractor modules have been removed from public
dispatch. This base type remains only as a structural protocol for any
future registry-backed extraction adapter that needs to return a
``DeclaracionFiling`` from a PDF path.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from ._schema import DeclaracionFiling, TemplateRevision


class DeclaracionExtractor(ABC):
    """Abstract extractor shape retained for registry-backed adapters.

    The legacy Python extractor registry is disabled, so this class no
    longer implies import-time registration or dispatch authority. The
    :meth:`extract` method is the only behavioural contract retained by
    the type.

    Attributes:
        template_revision: The :class:`TemplateRevision` identity the
            adapter reports for diagnostics.
    """

    template_revision: ClassVar[TemplateRevision]

    @abstractmethod
    def extract(self, pdf_path: Path) -> DeclaracionFiling:
        """Parse ``pdf_path`` into a strict :class:`DeclaracionFiling`.

        Args:
            pdf_path: Filesystem path of the source PDF.

        Returns:
            A :class:`DeclaracionFiling` populated with the resolved
            casillas, any extraction warnings, and provenance metadata
            (source path, SHA-256, parse timestamp).

        Raises:
            :exc:`aeat.adapters.inbound.declaracion._errors.DeclaracionParseError`:
                When the PDF cannot be parsed at the level the subclass
                requires (missing header field, unreadable bytes, etc.).
        """
