"""The registry refusal error used by edition delta tooling."""

from __future__ import annotations

from cadrumo.domain.calculations.registry.errors import RegistryError

__all__ = ("MigrationRefusedError",)
MigrationRefusedError = RegistryError
