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
- :class:`CertificateBackend` — preloads the operator certificate into
  the browser context.
- :class:`LocalCatalogueLoader` — loads the local authoritative
  modelo / portal manifest / filing history snapshots that the diffing
  classifier compares the live fetch against.
- :class:`SchemaLoader` / :class:`ModeloSchema` — schema lookup
  surface the runner forwards to per-strategy adapters.
- :class:`ManualRulesLoader` / :class:`Rule` — manual rule lookup
  surface used by escalation strategies.
- :class:`LLMClient` / :class:`LLMRequest` — an LLM probe the runner
  carries on its signature for forward compatibility, even though the
  happy path never invokes it.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

if TYPE_CHECKING:  # pragma: no cover - import side effects only
    from ...adapters.outbound.aeat.browser import BrowserSession


_MODELO_RE = re.compile(r"^\d{3}[A-Z]?$")
_PORTAL_RE = re.compile(r"^[a-z][a-z0-9_\-]{1,63}$")


class ModeloIdentifier(str):
    """Typed string identifier for an AEAT modelo (e.g. ``"100"``, ``"303"``).

    Format: three digits with an optional trailing uppercase letter.
    The shape mirrors :class:`aeat.domain.deadlines.ModeloIdentifier` and is
    intentionally wider than :class:`aeat.domain.modelos.ModeloCode` so live
    AEAT payloads referencing modelos outside the v1 closed catalogue
    can flow through the wire boundary without the runner crashing.
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
class CertificateBackend(Protocol):
    """Narrow surface over :mod:`aeat.adapters.outbound.aeat.adapters.outbound.aeat.auth.certificate` for the runner.

    Production wires this to
    :func:`aeat.adapters.outbound.aeat.adapters.outbound.aeat.auth.preload_into_browser_context`; tests substitute a
    concrete Protocol-conforming class that records calls.
    """

    async def preload_into_browser_context(self, session: BrowserSession) -> None:
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


@runtime_checkable
class ModeloSchema(Protocol):
    """Narrow shape returned by :class:`SchemaLoader`."""

    modelo: ModeloIdentifier


@runtime_checkable
class SchemaLoader(Protocol):
    """Narrow surface over :mod:`aeat.domain.schema` for the runner."""

    def load(self, modelo: ModeloIdentifier) -> ModeloSchema:
        """Return the extracted schema for a modelo."""
        ...


@runtime_checkable
class Rule(Protocol):
    """Narrow shape for a single manual rule from :mod:`aeat.domain.manuals`."""

    rule_id: str


@runtime_checkable
class ManualRulesLoader(Protocol):
    """Narrow surface over :mod:`aeat.domain.manuals` for the runner."""

    def load(self, modelo: ModeloIdentifier) -> tuple[Rule, ...]:
        """Return the manual rules for a modelo."""
        ...


@runtime_checkable
class LLMRequest(Protocol):
    """Narrow shape for a request to :mod:`aeat.adapters.outbound.llm`."""

    prompt: str


@runtime_checkable
class LLMClient(Protocol):
    """Narrow surface over :mod:`aeat.adapters.outbound.llm` for the runner.

    The runner does not invoke the LLM on its happy path, but it
    carries the Protocol on its signature so escalation strategies
    that consult the LLM can be wired in without changing the runner
    constructor.
    """

    async def complete(self, request: LLMRequest) -> str:
        """Return the completion for the given request."""
        ...
