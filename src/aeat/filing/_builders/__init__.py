"""Private builder implementations for :mod:`aeat.filing`.

Callers from outside :mod:`aeat.filing` MUST NOT import from this
package. Use :func:`aeat.filing.build_draft` instead.
"""

from __future__ import annotations

from .._builder import FilingBuilder
from .modelo_130 import Modelo130Builder

#: Registry of available builders, keyed by modelo string ID.
_BUILDER_REGISTRY: dict[str, type[FilingBuilder]] = {
    Modelo130Builder.modelo_id: Modelo130Builder,
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


__all__ = ["Modelo130Builder", "get_builder"]
