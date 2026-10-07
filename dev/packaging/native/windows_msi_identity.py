"""Windows Installer ownership identities, separate from the legacy combined family."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal
from uuid import NAMESPACE_DNS, UUID, uuid5

from .identity import DistributionIdentity, validate_native_version

InstallationScope = Literal["user", "machine"]
ProductRole = Literal["version", "registration"]


@dataclass(frozen=True)
class MsiIdentity:
    """A product release belongs to one role and scope; shared components outlive releases."""

    role: ProductRole
    scope: InstallationScope
    version: str
    product_code: str
    upgrade_code: str
    install_scope: str
    registry_root: str
    root_directory: str

    def component_code(self, relative: str) -> str:
        """Bind ownership to a canonical relative resource and its actual release location."""
        path = PurePosixPath(relative)
        if (
            not path.parts
            or path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != relative
            or "\\" in relative
            or ":" in relative
        ):
            raise ValueError("MSI component requires a canonical prefix-relative resource")
        resource = relative.casefold()
        if self.role == "version":
            resource = f"versions/{self.version}/{resource}"
        return str(uuid5(UUID(self.upgrade_code), f"component/{resource}")).upper()


def msi_identity(value: DistributionIdentity, scope: InstallationScope, role: ProductRole) -> MsiIdentity:
    """Preserve native scope semantics and keep new product families disjoint from legacy."""
    if value.target != "windows-x86-64":
        raise ValueError("Windows MSI requires the canonical Windows target")
    if scope not in {"user", "machine"} or role not in {"version", "registration"}:
        raise ValueError("Unsupported Windows MSI scope or ownership role")
    validate_native_version(value.version)
    namespace = uuid5(NAMESPACE_DNS, f"{value.application_id}/{value.target}/{scope}/msi/{role}")
    return MsiIdentity(
        role=role,
        scope=scope,
        version=value.version,
        product_code=str(uuid5(namespace, f"product/{value.version}")).upper(),
        upgrade_code=str(namespace).upper(),
        install_scope="perUser" if scope == "user" else "perMachine",
        registry_root="HKCU" if scope == "user" else "HKLM",
        root_directory="LocalAppDataFolder" if scope == "user" else "ProgramFiles64Folder",
    )
