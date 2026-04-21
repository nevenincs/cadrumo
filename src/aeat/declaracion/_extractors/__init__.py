"""Concrete per-modelo per-template-revision extractor registry."""

from __future__ import annotations

from .._errors import NoExtractorRegisteredError
from .._extractor import DeclaracionExtractor
from .._schema import TemplateRevision
from .modelo_111_v2025 import Modelo111V2025Extractor
from .modelo_115_v2025 import Modelo115V2025Extractor
from .modelo_130_v2025 import Modelo130V2025Extractor
from .modelo_180_v2025 import Modelo180V2025Extractor
from .modelo_190_v2025 import Modelo190V2025Extractor
from .modelo_303_v2024_09 import Modelo303V2024Orden819Extractor
from .modelo_303_v2025 import Modelo303V2025Extractor
from .modelo_347_v2025 import Modelo347V2025Extractor
from .modelo_390_v2025 import Modelo390V2025Extractor


def _key_for(extractor_cls: type[DeclaracionExtractor]) -> tuple[str, int, str]:
    tr = extractor_cls.template_revision
    return tr.modelo, tr.año, tr.revision


_REGISTERED_CLASSES: tuple[type[DeclaracionExtractor], ...] = (
    Modelo111V2025Extractor,
    Modelo115V2025Extractor,
    Modelo130V2025Extractor,
    Modelo180V2025Extractor,
    Modelo190V2025Extractor,
    Modelo303V2024Orden819Extractor,
    Modelo303V2025Extractor,
    Modelo347V2025Extractor,
    Modelo390V2025Extractor,
)

_REGISTRY: dict[tuple[str, int, str], type[DeclaracionExtractor]] = {_key_for(cls): cls for cls in _REGISTERED_CLASSES}


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
