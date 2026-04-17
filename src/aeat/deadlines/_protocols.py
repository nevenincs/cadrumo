"""Protocol stubs for cross-subpackage dependencies still in flight.

These Protocols let the deadline engine compile and ship before its
upstream subpackages land on ``main``:

- :class:`ModeloIdentifier` - rebase-swap stub for the real enum from
  ``aeat.models`` (issue #6). Mirrors the shape of
  ``aeat.sync._protocols.ModeloIdentifier`` so the rebase to #6 is
  mechanical and consistent across subpackages.
- :class:`ModeloCatalogueLoader` - rebase-swap stub for the catalogue
  loader from ``aeat.models``. The engine never imports
  ``aeat.models`` directly until #6 lands.
- :class:`CorpusReader` - optional rebase-swap stub for ``aeat.corpus``
  (issue #17). Supplies year-specific window overrides when present;
  the engine functions without it.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

if TYPE_CHECKING:  # pragma: no cover - import-cycle break
    from ._calendar import CanonicalWindow

_MODELO_RE = re.compile(r"^\d{3}[A-Z]?$")


class ModeloIdentifier(str):
    """Typed string identifier for an AEAT modelo (e.g. ``"100"``, ``"303"``).

    The format is intentionally permissive - three digits with an
    optional trailing uppercase letter - so the engine can compile
    standalone. The real enum from ``aeat.models`` will replace this
    stub on rebase of issue #6.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> ModeloIdentifier:
        if not isinstance(value, str) or not _MODELO_RE.match(value):
            raise ValueError(f"Invalid modelo identifier: {value!r}")
        return super().__new__(cls, value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(pattern=_MODELO_RE.pattern),
        )


@runtime_checkable
class ModeloCatalogueLoader(Protocol):
    """Rebase-swap stub for ``aeat.models`` catalogue access (issue #6).

    The engine only needs to know which modelos exist and to validate
    that a string identifier is part of the catalogue. The full modelo
    metadata surface (frequency, vigencia, labels) is fetched directly
    from the real ``aeat.models`` package once #6 merges.
    """

    def known_modelos(self) -> tuple[ModeloIdentifier, ...]:
        """Return the closed tuple of modelos in the catalogue."""
        ...

    def is_known(self, modelo: ModeloIdentifier) -> bool:
        """Return ``True`` iff ``modelo`` is part of the catalogue."""
        ...


@runtime_checkable
class CorpusReader(Protocol):
    """Rebase-swap stub for ``aeat.corpus`` (issue #17).

    Optional dependency. When supplied, the engine consults the corpus
    for year-specific window overrides published by AEAT (the
    *calendario del contribuyente*). When omitted, the engine falls
    back to its in-code canonical calendar table.
    """

    def load_year_overrides(self, year: int) -> tuple[CanonicalWindow, ...]:
        """Return the (possibly empty) tuple of overrides for ``year``."""
        ...
