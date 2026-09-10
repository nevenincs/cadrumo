"""Shared cache-policy constants for immutable bundled registry inputs."""

from __future__ import annotations

# Bundled package data is immutable for a running installed product. Development
# inputs outside that boundary are always re-scanned by their owning compiler.
BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS = 10.0

__all__ = ["BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS"]
