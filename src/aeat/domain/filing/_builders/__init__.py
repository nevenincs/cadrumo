"""Private builder implementations for :mod:`aeat.domain.filing`.

Callers from outside :mod:`aeat.domain.filing` MUST NOT import from this
package. Use :func:`aeat.application.filing.build_draft` instead.
"""

from __future__ import annotations

from .._builder import FilingBuilder
from .modelo_130 import Modelo130Builder
from .modelo_303 import Modelo303Builder
from .modelo_390 import QUARTERLY_303_INPUT_KEY, Modelo390Builder

#: Registry of available builders, keyed by modelo string ID.
_BUILDER_REGISTRY: dict[str, type[FilingBuilder]] = {
    Modelo130Builder.modelo_id: Modelo130Builder,
    Modelo303Builder.modelo_id: Modelo303Builder,
    Modelo390Builder.modelo_id: Modelo390Builder,
}


def get_builder(modelo: str) -> FilingBuilder:
    """Return a fresh builder instance for the given modelo ID.

    Args:
        modelo: Stable modelo string ID (e.g. ``"130"``).

    Returns:
        A new instance of the registered builder class.

    Raises:
        FilingBuilderError: When no builder is registered for the
            requested modelo.
    """
    from .._errors import FilingBuilderError

    builder_cls = _BUILDER_REGISTRY.get(modelo)
    if builder_cls is None:
        known = sorted(_BUILDER_REGISTRY)
        raise FilingBuilderError(f"No filing builder registered for modelo {modelo!r}. Known: {known}")
    return builder_cls()


__all__ = [
    "QUARTERLY_303_INPUT_KEY",
    "Modelo130Builder",
    "Modelo303Builder",
    "Modelo390Builder",
    "get_builder",
]
