"""Read-only portal discovery wrapping the domain registry.

:class:`PortalsService` exposes a local read surface over the immutable portal
registry. Each entry is identified by a :class:`Portal` value, carries a
:class:`PortalCategory` axis, and may be associated with a
:class:`ModeloCode` so callers can filter portal metadata without inspecting
the raw registry.

The service returns :class:`PortalRow` projections of
:class:`PortalMetadata`; it never opens URLs, checks reachability, requires a
live-read gate, or emits bucket events.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field

from ...core.errors.error_codes import get_registered_error_code
from ...core.errors.hierarchy import CadrumoError
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.modelos.codes import ModeloCode
from ...domain.portals.categories import PortalCategory
from ...domain.portals.codes import Portal
from ...domain.portals.metadata import PortalMetadata
from ...domain.portals.registry import PORTAL_REGISTRY


class PortalNotFoundError(CadrumoError):
    """Raised when portal lookup targets a :class:`Portal` absent from the registry.

    The refusal carries the class's registered locale key and the rejected
    identifier as a machine fact; it authors no sentence and names no command.
    Resolving the refusal means listing the catalogued portals, but that step is
    an operator-surface concern: the producer states the failed fact and the CLI
    boundary owns whichever action the catalogue can resolve for it.

    The key is read from the central error-code registry rather than repeated
    here, so this class carries no second spelling that could drift.

    Attributes:
        portal: The rejected portal identifier as supplied by the caller.
    """

    def __init__(self, *, portal: str) -> None:
        """Initialise from the rejected portal identifier alone."""
        super().__init__(
            context={"portal": portal},
            translated_message=get_registered_error_code(type(self)).message_key,
        )
        self.portal = portal


class PortalRow(BaseModel):
    """Operator-facing row in ``aeat app live portals list`` output.

    Slimmer than the underlying :class:`PortalMetadata`: we elide the
    translation-key indirection for notes and surface only the
    primary fields the operator can act on. The CLI renderer applies
    i18n where needed.
    """

    model_config = STRICT_FROZEN_CONFIG

    portal: Portal
    url: str = Field(min_length=1)
    category: PortalCategory
    auth_methods: tuple[str, ...] = Field(default_factory=tuple)
    url_stability: str = Field(min_length=1)
    active: bool
    replaced_by: Portal | None = None
    label_key: str = Field(min_length=1)
    purpose_key: str = Field(min_length=1)


def _portal_to_row(metadata: PortalMetadata) -> PortalRow:
    return PortalRow(
        portal=metadata.portal,
        url=str(metadata.url),
        category=metadata.category,
        auth_methods=tuple(sorted(m.value for m in metadata.auth_methods)),
        url_stability=metadata.url_stability.value,
        active=metadata.active,
        replaced_by=metadata.replaced_by,
        label_key=metadata.label,
        purpose_key=metadata.purpose,
    )


class PortalsService:
    """Local-only portal-registry read surface.

    No remote contact, no bucket events, no mutation. Pure projection
    over the immutable :data:`domain.portals.PORTAL_REGISTRY`.
    Injecting a registry supports tests and alternate catalogue snapshots
    while preserving the same :class:`Portal` to :class:`PortalMetadata`
    contract.
    """

    def __init__(self, registry: dict[Portal, PortalMetadata] | None = None) -> None:
        self._registry: dict[Portal, PortalMetadata] = dict(registry if registry is not None else PORTAL_REGISTRY)

    def list_portals(
        self,
        *,
        category: PortalCategory | None = None,
        modelo: ModeloCode | None = None,
        include_retired: bool = False,
    ) -> tuple[PortalRow, ...]:
        """Project the registry to operator-facing rows with optional filters.

        Args:
            category: When set, restricts rows to portals in that :class:`PortalCategory`.
            modelo: When set, restricts rows to portals associated with that :class:`ModeloCode`.
            include_retired: When ``True``, includes portals with ``active=False``.

        ``category`` and ``modelo`` are independent filters. Retired
        portals (``active=False``) are excluded by default; pass
        ``include_retired=True`` to surface them so the operator can
        trace where a deprecated URL was supposed to redirect to.

        Returns:
            tuple[:class:`PortalRow`, ...]: The list of portals.
        """
        entries: Iterable[PortalMetadata] = self._registry.values()
        if not include_retired:
            entries = (e for e in entries if e.active)
        if category is not None:
            entries = (e for e in entries if e.category is category)
        if modelo is not None:
            entries = (e for e in entries if modelo in getattr(e, "modelo_codes", ()))
        rows = tuple(_portal_to_row(metadata) for metadata in entries)
        return tuple(sorted(rows, key=lambda row: row.portal.value))

    def show(self, portal: Portal) -> PortalRow:
        """Return the :class:`PortalRow` for one :class:`Portal`.

        Raises :class:`PortalNotFoundError` when the requested portal code is
        absent from the injected registry.
        """
        metadata = self._registry.get(portal)
        if metadata is None:
            raise PortalNotFoundError(portal=portal.value)
        return _portal_to_row(metadata)


__all__ = [
    "PortalNotFoundError",
    "PortalRow",
    "PortalsService",
]
