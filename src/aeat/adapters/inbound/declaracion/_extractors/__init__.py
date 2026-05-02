"""Per-modelo, per-template-revision extractor registry.

Maps every supported ``(modelo, año, revision)`` triple to its concrete
:class:`aeat.adapters.inbound.declaracion._extractor.DeclaracionExtractor`
subclass. :func:`get_extractor` is the only public entry point — the
high-level :func:`aeat.adapters.inbound.declaracion.parse_declaracion`
routes the detected :class:`aeat.adapters.inbound.declaracion._schema.TemplateRevision`
through it to obtain a fresh extractor instance.

Adding a new modelo or template revision is mechanical: implement a
:class:`DeclaracionExtractor` subclass with its own ``template_revision``
ClassVar, import it into this module, and append the class to
``_REGISTERED_CLASSES``. Duplicate keys raise at import time via the
dict comprehension.
"""

from __future__ import annotations

from .._errors import NoExtractorRegisteredError
from .._extractor import DeclaracionExtractor
from .._parsers.modelo_100 import (
    Modelo100V2021LegacyExtractor,
    Modelo100V2022ModernExtractor,
    Modelo100V2023ModernExtractor,
)
from .._schema import TemplateRevision
from .modelo_036_v2025 import Modelo036V2025Extractor
from .modelo_037_v2025 import Modelo037V2025Extractor
from .modelo_111_v2025 import (
    Modelo111V2024Extractor,
    Modelo111V2025Extractor,
    Modelo111V2026Extractor,
)
from .modelo_115_v2025 import (
    Modelo115V2024Extractor,
    Modelo115V2025Extractor,
    Modelo115V2026Extractor,
)
from .modelo_123_v2025 import (
    Modelo123V2024Extractor,
    Modelo123V2025Extractor,
    Modelo123V2026Extractor,
)
from .modelo_130_v2025 import (
    Modelo130V2024Extractor,
    Modelo130V2025Extractor,
    Modelo130V2026Extractor,
)
from .modelo_131_v2025 import Modelo131V2025Extractor
from .modelo_180_v2025 import (
    Modelo180V2024Extractor,
    Modelo180V2025Extractor,
    Modelo180V2026Extractor,
)
from .modelo_190_v2025 import Modelo190V2025Extractor
from .modelo_193_v2025 import Modelo193V2025Extractor
from .modelo_200_v2025 import Modelo200V2025Extractor
from .modelo_202_v2025 import Modelo202V2025Extractor
from .modelo_232_v2025 import Modelo232V2025Extractor
from .modelo_303_v2024_09 import Modelo303V2024Orden819Extractor
from .modelo_303_v2025 import Modelo303V2025Extractor, Modelo303V2026Extractor
from .modelo_347_v2025 import Modelo347V2025Extractor
from .modelo_349_v2025 import Modelo349V2025Extractor
from .modelo_369_v2025 import Modelo369V2025Extractor
from .modelo_390_v2025 import (
    Modelo390V2024Extractor,
    Modelo390V2025Extractor,
    Modelo390V2026Extractor,
)
from .modelo_720_v2025 import Modelo720V2025Extractor
from .modelo_840_v2025 import Modelo840V2025Extractor


def _key_for(extractor_cls: type[DeclaracionExtractor]) -> tuple[str, int, str]:
    tr = extractor_cls.template_revision
    return tr.modelo, tr.año, tr.revision


_REGISTERED_CLASSES: tuple[type[DeclaracionExtractor], ...] = (
    Modelo036V2025Extractor,
    Modelo037V2025Extractor,
    Modelo100V2021LegacyExtractor,
    Modelo100V2022ModernExtractor,
    Modelo100V2023ModernExtractor,
    Modelo111V2024Extractor,
    Modelo111V2025Extractor,
    Modelo111V2026Extractor,
    Modelo115V2024Extractor,
    Modelo115V2025Extractor,
    Modelo115V2026Extractor,
    Modelo123V2024Extractor,
    Modelo123V2025Extractor,
    Modelo123V2026Extractor,
    Modelo130V2024Extractor,
    Modelo130V2025Extractor,
    Modelo130V2026Extractor,
    Modelo131V2025Extractor,
    Modelo180V2024Extractor,
    Modelo180V2025Extractor,
    Modelo180V2026Extractor,
    Modelo190V2025Extractor,
    Modelo193V2025Extractor,
    Modelo200V2025Extractor,
    Modelo202V2025Extractor,
    Modelo232V2025Extractor,
    Modelo303V2024Orden819Extractor,
    Modelo303V2025Extractor,
    Modelo303V2026Extractor,
    Modelo347V2025Extractor,
    Modelo349V2025Extractor,
    Modelo369V2025Extractor,
    Modelo390V2024Extractor,
    Modelo390V2025Extractor,
    Modelo390V2026Extractor,
    Modelo720V2025Extractor,
    Modelo840V2025Extractor,
)

_REGISTRY: dict[tuple[str, int, str], type[DeclaracionExtractor]] = {_key_for(cls): cls for cls in _REGISTERED_CLASSES}


def get_extractor(tr: TemplateRevision) -> DeclaracionExtractor:
    """Return a fresh extractor instance for the given template revision.

    Looks up the ``(modelo, año, revision)`` tuple in the internal
    registry and instantiates the matching
    :class:`aeat.adapters.inbound.declaracion._extractor.DeclaracionExtractor`
    subclass. Each call returns a new object, so extractor state never
    leaks between filings.

    Args:
        tr: The :class:`aeat.adapters.inbound.declaracion._schema.TemplateRevision`
            triple identifying the template.

    Returns:
        A fresh :class:`DeclaracionExtractor` ready to consume one PDF.

    Raises:
        :exc:`aeat.adapters.inbound.declaracion._errors.NoExtractorRegisteredError`:
            When no extractor is registered for the
            ``(modelo, año, revision)`` tuple. The message lists every
            supported triple to ease debugging.
    """
    cls = _REGISTRY.get((tr.modelo, tr.año, tr.revision))
    if cls is None:
        known = sorted(_REGISTRY.keys())
        raise NoExtractorRegisteredError(
            f"no declaración extractor for ({tr.modelo!r}, {tr.año}, {tr.revision!r}); supported: {known}"
        )
    return cls()


__all__ = ["get_extractor"]
