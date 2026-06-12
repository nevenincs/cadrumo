"""Read-only portal discovery wrapping the domain registry.

:class:`PortalsService` exposes a local read surface over the immutable portal
registry. Each entry is identified by a :class:`Portal` value and carries
a :class:`PortalCategory` axis so callers can filter by portal kind without
inspecting the raw registry.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from ...core.errors import AeatError
from ...core.i18n import tr
from ...domain.modelos import ModeloCode
from ...domain.portals import (
    PORTAL_REGISTRY,
    Portal,
    PortalCategory,
    PortalMetadata,
)


class PortalNotFoundError(AeatError):
    """Raised when ``aeat app live portals view`` targets an unknown portal."""


class PortalRow(BaseModel):
    """Operator-facing row in ``aeat app live portals list`` output.

    Slimmer than the underlying :class:`PortalMetadata` — we elide the
    translation-key indirection for notes and surface only the
    primary fields the operator can act on. The CLI renderer applies
    i18n where needed.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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
    over the immutable :data:`aeat.domain.portals.PORTAL_REGISTRY`.
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
            modelo: When set, restricts rows to portals associated with that modelo code.
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
        """Return the :class:`PortalRow` for one :class:`Portal`. Raises if the code is not registered."""
        metadata = self._registry.get(portal)
        if metadata is None:
            raise PortalNotFoundError(
                f"portal {portal!r} is not registered in PORTAL_REGISTRY",
                suggestion="aeat app live portals list",
                translated_message=tr("application.portals.errors.portal_not_found"),
            )
        return _portal_to_row(metadata)


__all__ = [
    "PortalNotFoundError",
    "PortalRow",
    "PortalsService",
]
