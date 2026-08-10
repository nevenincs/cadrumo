"""Errors raised by the storage-management service.

:class:`StorageReclaimRefusedError` is the loud half of the aggregate reclaim
guard. It names only the public area and the failed preflight property.

See Also:
    :func:`~cadrumo.application.storage_management.reclaim_storage_area`
        The guarded operation that raises it.
"""

from __future__ import annotations

from ...core import StorageArea
from ...core.errors import CadrumoError
from ...core.i18n import tr


class StorageManagementError(CadrumoError):
    """Base for refusals raised while inspecting or reclaiming the storage tree."""


class StorageReclaimRefusedError(StorageManagementError):
    """Refusal to delete an area that cannot pass the derived preflight."""

    def __init__(
        self,
        area: StorageArea,
        *,
        entry_count: int,
        reason: str,
    ) -> None:
        super().__init__(
            tr(
                "cli.config.storage.errors.reclaim_area_refused",
                default=("refusing to reclaim %{area}: %{reason}; nothing was removed."),
                area=area.value,
                entries=str(entry_count),
                reason=reason,
            ),
            context={
                "area": area.value,
                "entry_count": str(entry_count),
                "reason": reason,
            },
            suggestion="aeat config storage list",
        )
        self.area = area
        self.entry_count = entry_count
        self.reason = reason


class StorageReclaimUnconfirmedError(StorageManagementError):
    """Refusal to delete without an explicit confirmation from the caller.

    The confirmation lives at the service boundary, not only on the CLI flag, so
    a programmatic caller gets the same guarantee the operator's ``--yes`` buys.
    """

    def __init__(self, area: StorageArea, *, entry_count: int) -> None:
        super().__init__(
            tr(
                "cli.config.storage.errors.reclaim_area_unconfirmed",
                default=("reclaiming %{area} deletes up to %{entries} entries and needs explicit confirmation."),
                area=area.value,
                entries=str(entry_count),
            ),
            context={
                "area": area.value,
                "entry_count": str(entry_count),
            },
            suggestion="aeat config storage reclaim --yes",
        )
        self.area = area
        self.entry_count = entry_count


__all__ = [
    "StorageManagementError",
    "StorageReclaimRefusedError",
    "StorageReclaimUnconfirmedError",
]
