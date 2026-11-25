"""Open the canonical peer-verified runtime transport for installed service admission."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

from cadrumo.domain.calculations.registry.authority_location import published_authority_generation
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.deadline_budget import DEFAULT_TIMEOUT_POLICY, TimeoutDeadline
from cadrumo_client.transport.posix_endpoint import PosixEndpoint
from cadrumo_client.transport.product_version import installed_product_version
from cadrumo_client.transport.service_client import InstalledServiceClient
from cadrumo_client.transport.startup import LaunchDoor
from cadrumo_client.transport.windows import WindowsEndpoint

SERVICE_ID = "cadrumo-agent-service"


async def open_service_client(
    *, profile_id: UUID, storage_root: Path, timeout_deadline: TimeoutDeadline | None = None
) -> InstalledServiceClient:
    """Register this verified service connection without granting it a lease."""
    timeout_deadline = timeout_deadline or DEFAULT_TIMEOUT_POLICY.deadline()
    endpoint = (
        WindowsEndpoint(storage_root=storage_root)
        if sys.platform == "win32"
        else PosixEndpoint(storage_root=storage_root, create_namespace=False)
    )
    connection = None
    try:
        launch = LaunchDoor(
            endpoint,
            expected=ClientHello(
                lifecycle_notices="v1",
                product_version=installed_product_version(),
                storage_identity=endpoint.storage_identity,
                authority_generation=published_authority_generation(),
            ),
        )
        connection = await launch.open(timeout_deadline=timeout_deadline)
        client = InstalledServiceClient(
            connection=connection, profile_id=profile_id, service_id=SERVICE_ID, startup_deadline=timeout_deadline
        )
        client.claim()
        return client
    except BaseException:
        if connection is not None:
            connection.close()
        raise
    finally:
        endpoint.close()
