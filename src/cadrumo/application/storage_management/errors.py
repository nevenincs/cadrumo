"""Errors raised by the storage-management service.

:class:`StorageReclaimRefusedError` is the loud half of the aggregate reclaim
guard. It names only the public area and the failed preflight property.

See Also:
    :func:`~cadrumo.application.storage_management.reclaim_storage_area`
        The guarded operation that raises it.
"""

from __future__ import annotations

from ...core.storage_taxonomy import StorageArea
from ...core.errors.hierarchy import CadrumoError
from ...core.i18n import tr


class StorageManagementError(CadrumoError):
    """Base for refusals raised while inspecting or reclaiming the storage tree."""


def _area_display(area: StorageArea) -> str:
    """Return a localized text label while retaining the enum as the API value."""
    return tr(f"cli.config.storage.values.area.{area.value}", default=area.value)


_REASON_LOCALE_KEYS = {
    "the area contains durable state": "cli.config.storage.errors.reason.durable_state",
    "the taxonomy declares no reclaimable targets": "cli.config.storage.errors.reason.no_reclaimable_targets",
    "a selected target is not root-scoped": "cli.config.storage.errors.reason.not_root_scoped",
    "a selected target has a durable lifecycle": "cli.config.storage.errors.reason.durable_lifecycle",
    "a selected target contains protected declared data": "cli.config.storage.errors.reason.protected_descendant",
}


class StorageReclaimRefusedError(StorageManagementError):
    """Refusal to delete an area that cannot pass the derived preflight."""

    def __init__(
        self,
        area: StorageArea,
        *,
        entry_count: int,
        reason: str,
    ) -> None:
        """Initialize this public contract."""
        display_reason = tr(_REASON_LOCALE_KEYS[reason], default=reason)
        super().__init__(
            tr(
                "cli.config.storage.errors.reclaim_area_refused",
                default=("refusing to reclaim %{area}: %{reason}; nothing was removed."),
                area=_area_display(area),
                entries=str(entry_count),
                reason=display_reason,
            ),
            context={
                "area": area.value,
                "entry_count": str(entry_count),
                "reason": display_reason,
            },
        )
        self.area = area
        self.entry_count = entry_count
        self._reason = reason

    @property
    def reason(self) -> str:
        """Return the stable service reason while text rendering stays localized."""
        return self._reason


class StorageReclaimUnconfirmedError(StorageManagementError):
    """Refusal to delete without an explicit confirmation from the caller.

    The confirmation lives at the service boundary, not only on the CLI flag, so
    a programmatic caller gets the same guarantee the operator's ``--yes`` buys.
    """

    def __init__(self, area: StorageArea, *, entry_count: int) -> None:
        """Initialize this public contract."""
        super().__init__(
            tr(
                "cli.config.storage.errors.reclaim_area_unconfirmed",
                default=("reclaiming %{area} deletes up to %{entries} entries and needs explicit confirmation."),
                area=_area_display(area),
                entries=str(entry_count),
            ),
            context={
                "area": area.value,
                "entry_count": str(entry_count),
            },
        )
        self.area = area
        self.entry_count = entry_count


__all__ = [
    "StorageManagementError",
    "StorageReclaimRefusedError",
    "StorageReclaimUnconfirmedError",
]
