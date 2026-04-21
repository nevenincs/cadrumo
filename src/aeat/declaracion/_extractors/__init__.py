"""Concrete per-modelo per-template-revision extractor registry."""

from __future__ import annotations

from .._errors import NoExtractorRegisteredError
from .._extractor import DeclaracionExtractor
from .._schema import TemplateRevision
from .modelo_130_v2025 import Modelo130V2025Extractor

_REGISTRY: dict[tuple[str, int, str], type[DeclaracionExtractor]] = {
    (
        Modelo130V2025Extractor.template_revision.modelo,
        Modelo130V2025Extractor.template_revision.año,
        Modelo130V2025Extractor.template_revision.revision,
    ): Modelo130V2025Extractor,
}


def get_extractor(tr: TemplateRevision) -> DeclaracionExtractor:
    """Return a fresh extractor for the given template revision.

    Raises:
        NoExtractorRegisteredError: When no extractor is registered for
            the ``(modelo, año, revision)`` tuple.
    """
    cls = _REGISTRY.get((tr.modelo, tr.año, tr.revision))
    if cls is None:
        known = sorted(_REGISTRY.keys())
        raise NoExtractorRegisteredError(
            f"no declaración extractor for ({tr.modelo!r}, {tr.año}, {tr.revision!r}); supported: {known}"
        )
    return cls()


__all__ = ["get_extractor"]
