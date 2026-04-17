"""Protocol stubs for cross-subpackage dependencies that are still in flight.

Each Protocol declared in this module is a rebase-swap placeholder for a
subpackage that is being implemented on a sibling branch. Replacing a stub
with its real surface is intentionally a single, focused commit per issue:

- :class:`CertificateBackend` — #8 (``aeat.auth.certificate``)
- :class:`CorpusLoader` — #17 (``aeat.corpus``)
- :class:`SchemaLoader` / :class:`ModeloSchema` — #9 (``aeat.schema``)
- :class:`ManualRulesLoader` / :class:`Rule` — #25 (``aeat.manuals``)
- :class:`LLMClient` / :class:`LLMRequest` — #21 (``aeat.llm``)
- :class:`StorageBackendStub` — #10 (``aeat.storage``)
- :class:`ModeloIdentifier` — #6 (``aeat.models``)
- :class:`PortalIdentifier` — #7 (``aeat.portals``)

``aeat.browser.BrowserSession`` and ``aeat.i18n`` are NOT stubbed here:
both branches have merged to ``main`` and the runner imports them
directly.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

if TYPE_CHECKING:  # pragma: no cover - import side effects only
    from ..browser import BrowserSession


_MODELO_RE = re.compile(r"^\d{3}[A-Z]?$")
_PORTAL_RE = re.compile(r"^[a-z][a-z0-9_\-]{1,63}$")


class ModeloIdentifier(str):
    """Typed string identifier for an AEAT modelo (e.g. ``"100"``, ``"303"``).

    This type will be replaced by the real enum from ``aeat.models``
    (issue #6) on rebase. The format is intentionally permissive to let
    the runner compile standalone: three digits, optional trailing
    letter.
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

    This type will be replaced by the real enum from ``aeat.portals``
    (issue #7) on rebase.
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
    """Rebase-swap stub for ``aeat.auth.certificate`` (issue #8).

    The real surface will expose a ``LoadedCertificate`` type plus a
    ``preload_into_browser_context`` coroutine that injects the client
    certificate into a Playwright context before navigation.
    """

    async def preload_into_browser_context(self, session: BrowserSession) -> None:
        """Preload the certificate into the given browser session context."""
        ...


@runtime_checkable
class CorpusLoader(Protocol):
    """Rebase-swap stub for ``aeat.corpus`` (issue #17).

    Supplies the local-authoritative modelo / portal / history shapes
    the runner diffs against.
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
    """Rebase-swap stub for the schema shape returned by ``aeat.schema`` (#9)."""

    modelo: ModeloIdentifier


@runtime_checkable
class SchemaLoader(Protocol):
    """Rebase-swap stub for ``aeat.schema`` (issue #9)."""

    def load(self, modelo: ModeloIdentifier) -> ModeloSchema:
        """Return the extracted schema for a modelo."""
        ...


@runtime_checkable
class Rule(Protocol):
    """Rebase-swap stub for a single manual rule from ``aeat.manuals`` (#25)."""

    rule_id: str


@runtime_checkable
class ManualRulesLoader(Protocol):
    """Rebase-swap stub for ``aeat.manuals`` (issue #25)."""

    def load(self, modelo: ModeloIdentifier) -> tuple[Rule, ...]:
        """Return the manual rules for a modelo."""
        ...


@runtime_checkable
class LLMRequest(Protocol):
    """Rebase-swap stub for a request to ``aeat.llm`` (#21)."""

    prompt: str


@runtime_checkable
class LLMClient(Protocol):
    """Rebase-swap stub for ``aeat.llm`` (issue #21).

    The sync runner does not invoke the LLM on its happy path, but we
    carry the Protocol so the runner signature is stable across the
    rebase of #21.
    """

    async def complete(self, request: LLMRequest) -> str:
        """Return the completion for the given request."""
        ...


@runtime_checkable
class StorageBackendStub(Protocol):
    """Rebase-swap stub for ``aeat.storage`` (issue #10).

    Only used by :class:`aeat.sync.StorageDivergenceRepository` which
    raises :class:`NotImplementedError` until #10 merges.
    """

    def put(self, key: str, value: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...
