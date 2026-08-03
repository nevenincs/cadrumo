"""Errors raised by the storage-management service.

:class:`StorageReclaimRefusedError` is the loud half of the reclaim guard. It
carries the resolved path and the entry count alongside the declared lifecycle,
so a refusal tells the operator exactly what was *not* deleted and on whose
authority — a refusal that only says "no" trains the reader to retry with force.

See Also:
    :func:`~cadrumo.application.storage_management.reclaim_storage_category`
        The guarded operation that raises it.
"""

from __future__ import annotations

from pathlib import Path

from ...core import StorageCategory, StorageLifecycle
from ...core.errors import CadrumoError
from ...core.i18n import tr


class StorageManagementError(CadrumoError):
    """Base for refusals raised while inspecting or reclaiming the storage tree."""


class StorageReclaimRefusedError(StorageManagementError):
    """Refusal to delete a category whose declared lifecycle forbids it.

    The declared :class:`~cadrumo.core.StorageLifecycle` is the sole authority:
    a member declared unbounded by design holds the substrate a filing is
    defended with, and growth is the point rather than a leak to trim.
    """

    def __init__(
        self,
        category: StorageCategory,
        *,
        lifecycle: StorageLifecycle,
        path: Path | None,
        entry_count: int,
        reason: str,
    ) -> None:
        super().__init__(
            tr(
                "cli.config.storage.errors.reclaim_refused",
                default=(
                    "refusing to reclaim %{category}: %{reason}. "
                    "%{path} holds %{entries} entries and none were removed."
                ),
                category=category.value,
                reason=reason,
                path=str(path) if path is not None else "-",
                entries=str(entry_count),
            ),
            context={
                "category": category.value,
                "lifecycle": lifecycle.value,
                "path": str(path) if path is not None else "",
                "entry_count": str(entry_count),
                "reason": reason,
            },
            suggestion="aeat config storage list",
        )
        self.category = category
        self.lifecycle = lifecycle
        self.path = path
        self.entry_count = entry_count
        self.reason = reason


class StorageReclaimUnconfirmedError(StorageManagementError):
    """Refusal to delete without an explicit confirmation from the caller.

    The confirmation lives at the service boundary, not only on the CLI flag, so
    a programmatic caller gets the same guarantee the operator's ``--yes`` buys.
    """

    def __init__(self, category: StorageCategory, *, path: Path | None, entry_count: int) -> None:
        super().__init__(
            tr(
                "cli.config.storage.errors.reclaim_unconfirmed",
                default=(
                    "reclaiming %{category} deletes %{entries} entries under %{path} and needs explicit confirmation."
                ),
                category=category.value,
                entries=str(entry_count),
                path=str(path) if path is not None else "-",
            ),
            context={
                "category": category.value,
                "path": str(path) if path is not None else "",
                "entry_count": str(entry_count),
            },
            suggestion="aeat config storage reclaim --yes",
        )
        self.category = category
        self.path = path
        self.entry_count = entry_count


__all__ = [
    "StorageManagementError",
    "StorageReclaimRefusedError",
    "StorageReclaimUnconfirmedError",
]
