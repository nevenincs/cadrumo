"""Installation acts over the storage tree: where it is, whether it matches its declaration, what may go.

Each handler calls the application function the matching ``config storage``
command calls, so the terminal interface and MCP get the command line's work
and the command line's refusals. Each reply carries the members of the
document the command prints, projected by the same function, so an act and its
command print one document. The runtime's own settings name the storage root,
as they do for a command run in the same installation.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...application.runtime.installation_requests import (
    RuntimeStorageCheckReply,
    RuntimeStorageCheckRequest,
    RuntimeStorageInitReply,
    RuntimeStorageInitRequest,
    RuntimeStorageInventoryReply,
    RuntimeStorageInventoryRequest,
    RuntimeStorageReclaimReply,
    RuntimeStorageReclaimRequest,
)
from ...application.storage_management.documents import (
    ConfigStorageCheckResult,
    ConfigStorageInitResult,
    ConfigStorageListResult,
    ConfigStorageReclaimResult,
    ConfigStorageViewResult,
)
from ...application.storage_management.service import (
    collect_storage_area_inventory,
    inspect_storage_tree,
    materialise_storage_tree,
    reclaim_storage_area,
)
from .installation_composition import InstallationActRegistry
from .installation_door import InstallationActExchange


def _members(document: BaseModel) -> dict[str, object]:
    """Name each member of a command's document, so the reply carries exactly those."""
    return {name: getattr(document, name) for name in type(document).model_fields}


def _serve_inventory(
    request: RuntimeStorageInventoryRequest, exchange: InstallationActExchange
) -> RuntimeStorageInventoryReply:
    report = collect_storage_area_inventory()
    document = (
        ConfigStorageListResult.from_report(report)
        if request.area is None
        else ConfigStorageViewResult.from_report(report, request.area)
    )
    return exchange.reply(RuntimeStorageInventoryReply, **_members(document))


def _serve_check(request: RuntimeStorageCheckRequest, exchange: InstallationActExchange) -> RuntimeStorageCheckReply:
    del request
    return exchange.reply(
        RuntimeStorageCheckReply, **_members(ConfigStorageCheckResult.from_report(inspect_storage_tree()))
    )


def _serve_init(request: RuntimeStorageInitRequest, exchange: InstallationActExchange) -> RuntimeStorageInitReply:
    del request
    exchange.require_login()
    return exchange.reply(
        RuntimeStorageInitReply, **_members(ConfigStorageInitResult.from_report(materialise_storage_tree()))
    )


def _serve_reclaim(
    request: RuntimeStorageReclaimRequest, exchange: InstallationActExchange
) -> RuntimeStorageReclaimReply:
    exchange.require_login()
    report = reclaim_storage_area(request.area, confirmed=request.confirmed)
    return exchange.reply(RuntimeStorageReclaimReply, **_members(ConfigStorageReclaimResult.from_report(report)))


def register_storage_acts(registry: InstallationActRegistry) -> None:
    """Serve the four storage acts on ``registry``."""
    registry.register(RuntimeStorageInventoryRequest, _serve_inventory)
    registry.register(RuntimeStorageCheckRequest, _serve_check)
    registry.register(RuntimeStorageInitRequest, _serve_init)
    registry.register(RuntimeStorageReclaimRequest, _serve_reclaim)
