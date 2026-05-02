"""Narrow Protocol surfaces for the sync runner.

The runner is composed of read-only sub-systems that the test suite
exercises with concrete, hand-rolled Protocol-conforming classes (no
mocks, no patches). Each Protocol declares only the surface the runner
actually consumes:

- :class:`ModeloIdentifier` / :class:`PortalIdentifier` — typed,
  regex-validated string identifiers used at the live wire boundary.
  They intentionally accept any well-formed AEAT modelo / portal slug
  rather than the closed :class:`aeat.domain.modelos.ModeloCode` /
  :class:`aeat.domain.portals.Portal` enums; live AEAT data is the source of
  truth here, not our internal catalogue.
- :class:`CertificateContextPreloader` — preloads the operator certificate into
  the browser context.
- :class:`LocalCatalogueLoader` — loads the local authoritative
  modelo / portal manifest / filing history snapshots that the diffing
  classifier compares the live fetch against.
"""

from __future__ import annotations

import re
from typing import Any, Protocol, runtime_checkable

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .._identifiers import ModeloIdentifier

_PORTAL_RE = re.compile(r"^[a-z][a-z0-9_\-]{1,63}$")


class PortalIdentifier(str):
    """Typed string identifier for an AEAT portal slug.

    The wire-level slug shape (``"sede"``, ``"area-personal"``, ...) is
    distinct from the canonical :class:`aeat.domain.portals.Portal` enum
    values (``"portal_sede_root"``); this type captures whichever
    identifier AEAT publishes in its live portal manifest.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> PortalIdentifier:
        if not isinstance(value, str) or not _PORTAL_RE.match(value):
            raise ValueError(f"Invalid portal identifier: {value!r}")
        return super().__new__(cls, value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(pattern=_PORTAL_RE.pattern),
        )


@runtime_checkable
class CertificateContextPreloader(Protocol):
    """Narrow surface over :mod:`aeat.adapters.outbound.aeat.auth.certificate` for the runner.

    Production wires this to
    :func:`aeat.adapters.outbound.aeat.auth.preload_into_browser_context`; tests substitute a
    concrete Protocol-conforming class that records calls.
    """

    async def preload_into_browser_context(self, session: object) -> None:
        """Preload the certificate into the given browser session context."""
        ...


@runtime_checkable
class LocalCatalogueLoader(Protocol):
    """Loads local authoritative snapshots the runner diffs the live fetch against.

    The implementation owns where snapshots live on disk; the runner
    only consumes the typed shapes returned here.
    """

    def load_modelo(self, modelo: ModeloIdentifier) -> Any:
        """Return the local authoritative modelo snapshot."""
        ...

    def load_portal_manifest(self) -> Any:
        """Return the local authoritative portal manifest snapshot."""
        ...

    def load_filing_history(self, modelo: ModeloIdentifier) -> Any:
        """Return the local authoritative filing history snapshot."""
        ...
