"""Abstract base class for per-modelo declaración extractors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from ._schema import DeclaracionFiling, TemplateRevision


class DeclaracionExtractor(ABC):
    """One concrete extractor per ``(modelo, template_revision)``."""

    template_revision: ClassVar[TemplateRevision]

    @abstractmethod
    def extract(self, pdf_path: Path) -> DeclaracionFiling:
        """Return a strict :class:`DeclaracionFiling` for ``pdf_path``."""
