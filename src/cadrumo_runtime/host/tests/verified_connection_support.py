"""Verified client connections to a test runtime endpoint."""

from __future__ import annotations

import time
from importlib.metadata import version

from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.windows import WindowsEndpoint


def connect_test_client(endpoint: WindowsEndpoint) -> VerifiedConnection:
    """Open a verified connection that presents the synthetic ``test`` product version."""
    return VerifiedConnection(
        endpoint.connect(timeout=3),
        expected=ClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def connect_installed_client(endpoint: WindowsEndpoint) -> VerifiedConnection:
    """Open a verified connection that presents the installed ``cadrumo`` distribution version."""
    return VerifiedConnection(
        endpoint.connect(timeout=3),
        expected=ClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )
