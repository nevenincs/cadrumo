"""MSI resource ownership must separate releases, roles, scopes and channels."""

from dataclasses import replace
from uuid import UUID

import pytest

from dev.packaging.native.identity import identity
from dev.packaging.native.windows_msi_identity import InstallationScope, msi_identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_product_families_separate_roles_scopes_channels_and_legacy() -> None:
    values = [
        msi_identity(identity("windows-x86-64", channel), scope, role)
        for channel in ("stable", "preview")
        for scope in ("user", "machine")
        for role in ("version", "registration")
    ]
    assert len({value.upgrade_code for value in values}) == 8
    assert len({value.product_code for value in values}) == 8
    legacy = identity("windows-x86-64").upgrade_code
    assert legacy == "9AA7A3AF-0C16-5672-8C22-1BA49EC0F757"
    assert legacy not in {value.upgrade_code for value in values}
    for value in values:
        assert UUID(value.product_code).version == 5
        assert UUID(value.upgrade_code).version == 5


@pytest.mark.parametrize("scope", ["user", "machine"])
def test_shared_components_keep_identity_while_version_components_change(scope: InstallationScope) -> None:
    value = identity("windows-x86-64")
    old = replace(value, version="1.0.0")
    new = replace(value, version="1.1.0")
    old_version = msi_identity(old, scope, "version")
    new_version = msi_identity(new, scope, "version")
    old_registration = msi_identity(old, scope, "registration")
    new_registration = msi_identity(new, scope, "registration")
    for first, second in [(old_version, new_version), (old_registration, new_registration)]:
        assert first.product_code != second.product_code
        assert first.upgrade_code == second.upgrade_code
    assert old_version.component_code("cadrumo-manager.exe") != new_version.component_code("cadrumo-manager.exe")
    assert old_registration.component_code("cadrumo-manager.exe") == new_registration.component_code(
        "cadrumo-manager.exe"
    )
    assert new_registration.component_code("cadrumo-manager.exe") != new_version.component_code("cadrumo-manager.exe")
    assert new_registration.component_code("docs/licenses/NOTICE.txt") != new_registration.component_code("NOTICE.txt")
    assert new_registration.component_code("NOTICE.txt") == new_registration.component_code("notice.TXT")
    assert msi_identity(old, scope, "registration") == old_registration


@pytest.mark.parametrize(
    "scope,install_scope,registry_root,root_directory",
    [
        ("user", "perUser", "HKCU", "LocalAppDataFolder"),
        ("machine", "perMachine", "HKLM", "ProgramFiles64Folder"),
    ],
)
def test_scopes_choose_native_privilege_registry_and_root(
    scope: InstallationScope, install_scope: str, registry_root: str, root_directory: str
) -> None:
    value = msi_identity(identity("windows-x86-64"), scope, "version")
    assert (value.install_scope, value.registry_root, value.root_directory) == (
        install_scope,
        registry_root,
        root_directory,
    )


@pytest.mark.parametrize(
    "resource", ["", ".", "../cadrumo.exe", "/cadrumo.exe", "C:/cadrumo.exe", "docs\\x", "docs//x", "docs/./x"]
)
def test_noncanonical_component_resources_are_rejected(resource: str) -> None:
    value = msi_identity(identity("windows-x86-64"), "user", "version")
    with pytest.raises(ValueError, match="canonical prefix-relative"):
        value.component_code(resource)


@pytest.mark.parametrize("version", ["01.0.0", "1.0.0.preview", "256.0.0", "1.256.0", "1.0.65536"])
def test_msi_identity_reuses_canonical_version_constraints(version: str) -> None:
    value = replace(identity("windows-x86-64"), version=version)
    with pytest.raises(ValueError):
        msi_identity(value, "machine", "registration")


def test_non_windows_products_are_refused() -> None:
    with pytest.raises(ValueError, match="canonical Windows target"):
        msi_identity(identity("linux-x86-64"), "user", "version")
