"""Present the exact application setup plan to the person reviewing it."""

from __future__ import annotations

from typing import Final

from ....application.components_operations import ProvisionPlan
from ....application.dependency_contracts import DependencyItemDeclaration
from ....application.dependency_registry import dependency_item_declarations
from ....application.dependency_wording import dependency_space_sentence
from ....core.i18n.render import tr
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path

_MIB: Final = 1024**2
_GIB: Final = 1024**3


def _declaration(item_id: str) -> DependencyItemDeclaration:
    return next(declaration for declaration in dependency_item_declarations() if declaration.item_id == item_id)


def _item_name(item_id: str) -> str:
    return tr(f"application.{_declaration(item_id).display_key}")


def _size(value: int) -> str:
    if value >= _GIB:
        return tr("tui.setup.size.gigabytes", value=f"{value / _GIB:.1f}")
    return tr("tui.setup.size.megabytes", value=f"{max(1, round(value / _MIB))}")


def _space_sentence(plan: ProvisionPlan) -> str:
    free = "?" if plan.space.free_bytes is None else _size(plan.space.free_bytes)
    return dependency_space_sentence(required=_size(plan.space.required_bytes), free=free)


def _destination(destination: str | None) -> str | None:
    """Say where a plan stores what it downloads, for the destinations that are storage locations."""
    if destination is None:
        return None
    try:
        category = StorageCategory(destination)
    except ValueError:
        return None
    return tr("tui.setup.plan.destination", path=str(storage_path(category)))


def setup_review_text(plan: ProvisionPlan) -> str:
    """Word a setup plan for the person who approves it: what, how large, from where, and where."""
    unknown = tr("tui.setup.plan.size_unknown")
    lines = [tr("tui.setup.plan.heading")]
    for entry in plan.entries:
        size = unknown if entry.download_bytes is None else _size(entry.download_bytes)
        lines.append(
            tr("tui.setup.plan.entry", name=_item_name(entry.item_id), size=size, hosts=", ".join(entry.source_hosts))
        )
        destination = _destination(None if entry.destination is None else entry.destination)
        if destination is not None:
            lines.append(destination)
        if entry.installs_outside_program:
            lines.append(tr("tui.setup.plan.installs_program"))
    total_key = "tui.setup.plan.total_unknown" if plan.has_unknown_size else "tui.setup.plan.total"
    lines.append(tr(total_key, size=_size(plan.known_download_bytes)))
    if not plan.space.sufficient:
        lines.append(_space_sentence(plan))
    return "\n".join(lines)
