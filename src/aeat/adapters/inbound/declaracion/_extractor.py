"""Abstract base class for per-modelo declaración extractors.

Defines the :class:`DeclaracionExtractor` contract that every concrete
extractor under :mod:`aeat.adapters.inbound.declaracion._extractors`
implements. Subclasses pin a :class:`TemplateRevision` ClassVar and
implement :meth:`DeclaracionExtractor.extract` to convert the PDF at
``pdf_path`` into a strict :class:`DeclaracionFiling`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from ._schema import DeclaracionFiling, TemplateRevision


class DeclaracionExtractor(ABC):
    """Abstract extractor for a single ``(modelo, template_revision)`` pair.

    Each concrete subclass owns the parsing logic for one AEAT template
    revision and is registered in
    :mod:`aeat.adapters.inbound.declaracion._extractors`. The
    :meth:`extract` method is the only behavioural contract; everything
    else (regex maps, field labels, structural checks) is an internal
    detail of the subclass.

    Attributes:
        template_revision: The :class:`TemplateRevision` triple this
            extractor handles. Used by
            :func:`aeat.adapters.inbound.declaracion._extractors.get_extractor`
            to route a detected PDF to the right extractor.
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
