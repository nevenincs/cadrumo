"""Client SDK logging enrollment for the hosting process."""

from __future__ import annotations

from cadrumo.core.logging import register_first_party_logger


def register_client_logging_namespace() -> None:
    """Enroll client SDK diagnostics before the host configures logging."""
    register_first_party_logger("cadrumo_client")
