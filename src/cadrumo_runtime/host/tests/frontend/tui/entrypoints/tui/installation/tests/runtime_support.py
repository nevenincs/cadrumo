"""A real runtime that serves this test's own handlers, and the real client that reaches it.

The native transport, the connection service, the installation door and the
client are the real ones. Only the handlers behind the door are the test's, so
each records exactly what crossed the wire to it.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from threading import Event
from uuid import uuid4

from cadrumo.application.config_reset import require_config_reset_confirmation
from cadrumo.application.diagnostics_repair_documents import RepairProfileHealthDocument
from cadrumo.application.storage_management.documents import StorageAreaPayload
from cadrumo.application.storage_management.errors import StorageReclaimUnconfirmedError
from cadrumo.application.storage_management.models import StorageAreaDisposition, StorageOccupancy
from cadrumo.core.storage_taxonomy import StorageArea
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.installation_requests import (
    ArchiveImportPrepareReply,
    ArchiveImportPrepareRequest,
    ArchiveImportReply,
    ArchiveImportRequest,
    InstallationPassphrase,
    ProfileListReply,
    ProfileListRequest,
    ProfileListRow,
    RepairProfileReply,
    RepairProfileRequest,
    ResetStartReply,
    ResetStartRequest,
    ResetStatusReply,
    ResetStatusRequest,
    StorageCheckRequest,
    StorageInitRequest,
    StorageInventoryReply,
    StorageInventoryRequest,
    StorageReclaimReply,
    StorageReclaimRequest,
)
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.installation_client import InstallationClient
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.tests.profile_worker_support import owner_id
from cadrumo_runtime.host.installation_composition import InstallationActRegistry
from cadrumo_runtime.host.installation_door import InstallationActExchange
from cadrumo_runtime.host.tests.installation_registered_runtime import serving_registered_runtime
from cadrumo_runtime.host.tests.installation_runtime import InstallationLogin, serve_check, serve_fault

RECLAIMABLE_ENTRIES = 3
"""How many entries the synthetic reclaim says a confirmed act would remove."""


@dataclass
class ServedActs:
    """What the test's handlers saw, and the gate one of them waits on."""

    inventories: list[StorageArea | None] = field(default_factory=list)
    reclaims: list[tuple[StorageArea, bool]] = field(default_factory=list)
    prepared: list[tuple[str, str]] = field(default_factory=list)
    imported: list[tuple[str, str, str]] = field(default_factory=list)
    passphrases: list[str] = field(default_factory=list)
    repairs: list[tuple[str | None, bool, bool]] = field(default_factory=list)
    resets: list[bool] = field(default_factory=list)
    reset_status_reads: int = 0
    import_reached: Event = field(default_factory=Event)
    release_import: Event = field(default_factory=Event)

    def __post_init__(self) -> None:
        """Leave the import ungated unless a test closes the gate."""
        self.release_import.set()

    def register(self, registry: InstallationActRegistry) -> None:
        """Register the handlers; every other act stays without one."""
        registry.register(StorageCheckRequest, serve_check)
        registry.register(StorageInitRequest, serve_fault)
        registry.register(StorageInventoryRequest, self._inventory)
        registry.register(StorageReclaimRequest, self._reclaim)
        registry.register(ProfileListRequest, self._profiles)
        registry.register(ArchiveImportPrepareRequest, self._prepare)
        registry.register(ArchiveImportRequest, self._import)
        registry.register(RepairProfileRequest, self._repair)
        registry.register(ResetStartRequest, self._reset_start)
        registry.register(ResetStatusRequest, self._reset_status)

    def _inventory(self, request: StorageInventoryRequest, exchange: InstallationActExchange) -> StorageInventoryReply:
        cache = StorageAreaPayload(
            area=StorageArea.CACHE,
            occupancy=StorageOccupancy.POPULATED,
            disposition=StorageAreaDisposition.RECLAIMABLE,
            resolved_paths=1,
            entry_count=RECLAIMABLE_ENTRIES,
            footprint_bytes=4096,
            reclaimable=True,
        )
        self.inventories.append(request.area)
        if request.area is None:
            return exchange.reply(StorageInventoryReply, storage_root=str(exchange.storage_root), areas=[cache])
        return exchange.reply(StorageInventoryReply, storage_root=str(exchange.storage_root), area=cache)

    def _reclaim(self, request: StorageReclaimRequest, exchange: InstallationActExchange) -> StorageReclaimReply:
        self.reclaims.append((request.area, request.confirmed))
        if not request.confirmed:
            raise StorageReclaimUnconfirmedError(request.area, entry_count=RECLAIMABLE_ENTRIES)
        exchange.changes_begin()
        return exchange.reply(
            StorageReclaimReply, area=request.area, target_count=1, removed_entries=RECLAIMABLE_ENTRIES
        )

    def _profiles(self, request: ProfileListRequest, exchange: InstallationActExchange) -> ProfileListReply:
        del request
        return exchange.reply(
            ProfileListReply,
            active_profile="Synthetic profile",
            profiles=(ProfileListRow(name="Synthetic profile", bucket_id="[hidden]", active=True),),
        )

    def _prepare(
        self, request: ArchiveImportPrepareRequest, exchange: InstallationActExchange
    ) -> ArchiveImportPrepareReply:
        self.prepared.append((request.label, request.path))
        return exchange.reply(ArchiveImportPrepareReply, source_digest=source_digest_of(request.path))

    def _import(self, request: ArchiveImportRequest, exchange: InstallationActExchange) -> ArchiveImportReply:
        secrets = exchange.receive_secret(InstallationPassphrase)
        self.imported.append((request.label, request.path, request.source_digest))
        self.passphrases.append(secrets.passphrase.get_secret_value())
        self.import_reached.set()
        if not self.release_import.wait(20):
            raise TimeoutError("the synthetic import was never released")
        exchange.changes_begin()
        return exchange.reply(
            ArchiveImportReply,
            profile_id=str(uuid4()),
            label=request.label,
            authority="password",
            recovery_enrolled=False,
        )

    def _repair(self, request: RepairProfileRequest, exchange: InstallationActExchange) -> RepairProfileReply:
        self.repairs.append((request.profile, request.clear_active, request.confirmed))
        health = RepairProfileHealthDocument(active_profile=None, source="none", status="no_active_profile")
        cleared = request.clear_active and request.confirmed
        if cleared:
            exchange.changes_begin()
        return exchange.reply(
            RepairProfileReply,
            dry_run=not cleared,
            cleared_pointer=cleared,
            before=health,
            after=health if cleared else None,
        )

    def _reset_start(self, request: ResetStartRequest, exchange: InstallationActExchange) -> ResetStartReply:
        del exchange
        self.resets.append(request.confirmed)
        require_config_reset_confirmation(request.confirmed)
        raise AssertionError("the synthetic runtime never carries a reset out")

    def _reset_status(self, request: ResetStatusRequest, exchange: InstallationActExchange) -> ResetStatusReply:
        del request
        self.reset_status_reads += 1
        return exchange.reply(ResetStatusReply, operation=None)


def source_digest_of(path: str) -> str:
    """The digest the synthetic prepare read answers for one source path."""
    return sha256(path.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ServedRuntime:
    """One serving runtime, its storage root, and what its handlers saw."""

    endpoint: WindowsEndpoint
    root: Path
    acts: ServedActs

    async def open_client(self) -> InstallationClient:
        """Open a real verified installation connection to this runtime."""
        return await asyncio.to_thread(installation_client, self.endpoint)


def installation_client(endpoint: WindowsEndpoint) -> InstallationClient:
    """Connect the real client to a test runtime, which announces the test cohort's version."""
    return InstallationClient(
        VerifiedConnection(
            endpoint.connect(timeout=3),
            expected=ClientHello(product_version="test", storage_identity=endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
    )


@contextmanager
def serving_test_acts(tmp_path: Path) -> Generator[ServedRuntime]:
    """Serve the test's handlers over the real transport until the scope ends."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    acts = ServedActs()
    try:
        with serving_registered_runtime(endpoint, root, InstallationLogin(owner=owner_id()), acts.register):
            yield ServedRuntime(endpoint, root, acts)
    finally:
        acts.release_import.set()
        endpoint.close()

