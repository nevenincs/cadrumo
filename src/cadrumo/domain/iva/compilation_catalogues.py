"""The catalogues a registry compilation validates IVA grounding against.

Runtime reads catalogue facts only from the signed authority artifact. Compiling
that authority checks IVA grounding before any artifact can exist, so the
compiler scopes the check to the catalogues it is compiling. Outside that scope
nothing is supplied and the signed artifact remains the only source.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..calculations.registry.schema_references import LegalReference, SourceReference

__all__ = ["CompilationCatalogues", "compiling_catalogues", "compiling_catalogues_in_scope"]

type CompilationCatalogues = tuple[Mapping[str, LegalReference], Mapping[str, SourceReference], Path]

_COMPILING_CATALOGUES: ContextVar[CompilationCatalogues | None] = ContextVar("compiling_catalogues", default=None)


@contextmanager
def compiling_catalogues(
    legal: Mapping[str, LegalReference],
    sources: Mapping[str, SourceReference],
    source_root: Path,
) -> Iterator[None]:
    """Scope IVA grounding to the catalogues of the authority being compiled."""
    token = _COMPILING_CATALOGUES.set((legal, sources, source_root))
    try:
        yield
    finally:
        _COMPILING_CATALOGUES.reset(token)


def compiling_catalogues_in_scope() -> CompilationCatalogues | None:
    """Return the catalogues of the compilation in progress, or ``None`` outside one."""
    return _COMPILING_CATALOGUES.get()
