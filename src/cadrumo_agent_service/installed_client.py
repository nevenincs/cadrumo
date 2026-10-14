"""Open the canonical peer-verified runtime transport for installed service admission."""

from __future__ import annotations

import sys
from importlib.metadata import version
from pathlib import Path
from uuid import UUID

from cadrumo.domain.calculations.registry.authority_location import published_authority_generation
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.transport.posix_endpoint import PosixEndpoint
from cadrumo_client.transport.service_client import InstalledServiceClient
from cadrumo_client.transport.startup import LaunchDoor
from cadrumo_client.transport.windows import WindowsEndpoint

SERVICE_ID = "cadrumo-agent-service"


async def open_service_client(*, profile_id: UUID, storage_root: Path) -> InstalledServiceClient:
    """Register this verified service connection without granting it a lease."""
    endpoint = (
        WindowsEndpoint(storage_root=storage_root)
        if sys.platform == "win32"
        else PosixEndpoint(storage_root=storage_root)
    )
    connection = None
    try:
        launch = LaunchDoor(
            endpoint,
            expected=ClientHello(
                lifecycle_notices="v1",
                product_version=version("cadrumo"),
                storage_identity=endpoint.storage_identity,
                authority_generation=published_authority_generation(),
            ),
        )
        connection = await launch.open()
        client = InstalledServiceClient(connection=connection, profile_id=profile_id, service_id=SERVICE_ID)
        client.claim()
        return client
    except BaseException:
        if connection is not None:
            connection.close()
        raise
    finally:
        endpoint.close()
