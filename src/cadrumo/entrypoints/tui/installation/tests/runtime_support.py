"""A real runtime that serves this test's own handlers, and the real client that reaches it.

The native transport, the connection service, the installation door and the
client are the real ones. Only the handlers behind the door are the test's, so
each records exactly what crossed the wire to it.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from threading import Event
from uuid import uuid4

from textual.pilot import Pilot

from .....adapters.local_runtime.framing import VerifiedRuntimeConnection
from .....adapters.local_runtime.installation_client import RuntimeInstallationClient
from .....adapters.local_runtime.tests.profile_worker_support import owner_id
from .....adapters.local_runtime.windows import WindowsRuntimeEndpoint
from .....application.config_reset import require_config_reset_confirmation
from .....application.diagnostics_repair_documents import RepairProfileHealthDocument
from .....application.runtime.contracts import RuntimeClientHello
from .....application.runtime.installation_requests import (
    RuntimeArchiveImportPrepareReply,
    RuntimeArchiveImportPrepareRequest,
    RuntimeArchiveImportReply,
    RuntimeArchiveImportRequest,
    RuntimeInstallationPassphrase,
    RuntimeProfileListReply,
    RuntimeProfileListRequest,
    RuntimeProfileListRow,
    RuntimeRepairProfileReply,
    RuntimeRepairProfileRequest,
    RuntimeResetStartReply,
    RuntimeResetStartRequest,
    RuntimeResetStatusReply,
    RuntimeResetStatusRequest,
    RuntimeStorageCheckRequest,
    RuntimeStorageInitRequest,
    RuntimeStorageInventoryReply,
    RuntimeStorageInventoryRequest,
    RuntimeStorageReclaimReply,
    RuntimeStorageReclaimRequest,
)
from .....application.storage_management.documents import StorageAreaPayload
from .....application.storage_management.errors import StorageReclaimUnconfirmedError
from .....application.storage_management.models import StorageAreaDisposition, StorageOccupancy
from .....core.storage_taxonomy import StorageArea
from ....runtime.installation_composition import InstallationActRegistry
from ....runtime.installation_door import InstallationActExchange
from ....runtime.tests.installation_registered_runtime import serving_registered_runtime
from ....runtime.tests.installation_runtime import InstallationLogin, serve_check, serve_fault

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
        registry.register(RuntimeStorageCheckRequest, serve_check)
        registry.register(RuntimeStorageInitRequest, serve_fault)
        registry.register(RuntimeStorageInventoryRequest, self._inventory)
        registry.register(RuntimeStorageReclaimRequest, self._reclaim)
        registry.register(RuntimeProfileListRequest, self._profiles)
        registry.register(RuntimeArchiveImportPrepareRequest, self._prepare)
        registry.register(RuntimeArchiveImportRequest, self._import)
        registry.register(RuntimeRepairProfileRequest, self._repair)
        registry.register(RuntimeResetStartRequest, self._reset_start)
        registry.register(RuntimeResetStatusRequest, self._reset_status)

    def _inventory(
        self, request: RuntimeStorageInventoryRequest, exchange: InstallationActExchange
    ) -> RuntimeStorageInventoryReply:
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
            return exchange.reply(RuntimeStorageInventoryReply, storage_root=str(exchange.storage_root), areas=[cache])
        return exchange.reply(RuntimeStorageInventoryReply, storage_root=str(exchange.storage_root), area=cache)

    def _reclaim(
        self, request: RuntimeStorageReclaimRequest, exchange: InstallationActExchange
    ) -> RuntimeStorageReclaimReply:
        self.reclaims.append((request.area, request.confirmed))
        if not request.confirmed:
            raise StorageReclaimUnconfirmedError(request.area, entry_count=RECLAIMABLE_ENTRIES)
        return exchange.reply(
            RuntimeStorageReclaimReply, area=request.area, target_count=1, removed_entries=RECLAIMABLE_ENTRIES
        )

    def _profiles(
        self, request: RuntimeProfileListRequest, exchange: InstallationActExchange
    ) -> RuntimeProfileListReply:
        del request
        return exchange.reply(
            RuntimeProfileListReply,
            active_profile="Synthetic profile",
            profiles=(RuntimeProfileListRow(name="Synthetic profile", bucket_id="[hidden]", active=True),),
        )

    def _prepare(
        self, request: RuntimeArchiveImportPrepareRequest, exchange: InstallationActExchange
    ) -> RuntimeArchiveImportPrepareReply:
        self.prepared.append((request.label, request.path))
        return exchange.reply(RuntimeArchiveImportPrepareReply, source_digest=source_digest_of(request.path))

    def _import(
        self, request: RuntimeArchiveImportRequest, exchange: InstallationActExchange
    ) -> RuntimeArchiveImportReply:
        secrets = exchange.receive_secret(RuntimeInstallationPassphrase)
        self.imported.append((request.label, request.path, request.source_digest))
        self.passphrases.append(secrets.passphrase.get_secret_value())
        self.import_reached.set()
        if not self.release_import.wait(20):
            raise TimeoutError("the synthetic import was never released")
        return exchange.reply(
            RuntimeArchiveImportReply,
            profile_id=str(uuid4()),
            label=request.label,
            authority="password",
            recovery_enrolled=False,
        )

    def _repair(
        self, request: RuntimeRepairProfileRequest, exchange: InstallationActExchange
    ) -> RuntimeRepairProfileReply:
        self.repairs.append((request.profile, request.clear_active, request.confirmed))
        health = RepairProfileHealthDocument(active_profile=None, source="none", status="no_active_profile")
        cleared = request.clear_active and request.confirmed
        return exchange.reply(
            RuntimeRepairProfileReply,
            dry_run=not cleared,
            cleared_pointer=cleared,
            before=health,
            after=health if cleared else None,
        )

    def _reset_start(
        self, request: RuntimeResetStartRequest, exchange: InstallationActExchange
    ) -> RuntimeResetStartReply:
        del exchange
        self.resets.append(request.confirmed)
        require_config_reset_confirmation(request.confirmed)
        raise AssertionError("the synthetic runtime never carries a reset out")

    def _reset_status(
        self, request: RuntimeResetStatusRequest, exchange: InstallationActExchange
    ) -> RuntimeResetStatusReply:
        del request
        self.reset_status_reads += 1
        return exchange.reply(RuntimeResetStatusReply, operation=None)


def source_digest_of(path: str) -> str:
    """The digest the synthetic prepare read answers for one source path."""
    return sha256(path.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ServedRuntime:
    """One serving runtime, its storage root, and what its handlers saw."""

    endpoint: WindowsRuntimeEndpoint
    root: Path
    acts: ServedActs

    async def open_client(self) -> RuntimeInstallationClient:
        """Open a real verified installation connection to this runtime."""
        return await asyncio.to_thread(installation_client, self.endpoint)


def installation_client(endpoint: WindowsRuntimeEndpoint) -> RuntimeInstallationClient:
    """Connect the real client to a test runtime, which announces the test cohort's version."""
    return RuntimeInstallationClient(
        VerifiedRuntimeConnection(
            endpoint.connect(timeout=3),
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
    )


@contextmanager
def serving_test_acts(tmp_path: Path) -> Iterator[ServedRuntime]:
    """Serve the test's handlers over the real transport until the scope ends."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    acts = ServedActs()
    try:
        with serving_registered_runtime(endpoint, root, InstallationLogin(owner=owner_id()), acts.register):
            yield ServedRuntime(endpoint, root, acts)
    finally:
        acts.release_import.set()
        endpoint.close()


async def until(pilot: Pilot[None], condition: Callable[[], bool], *, seconds: float = 15) -> None:
    """Let the interface run until ``condition`` holds."""
    async with asyncio.timeout(seconds):
        while not condition():
            await pilot.pause(0.02)
