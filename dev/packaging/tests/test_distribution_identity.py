"""Installation identity must survive upgrades without merging release channels."""

from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.native.identity import cmake_projection, identity
from dev.packaging.runtime_wheelhouse_contract import SUPPORTED_TARGETS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("target", [item.name for item in SUPPORTED_TARGETS])
def test_upgrade_family_survives_product_version_change(target: str, tmp_path: Path) -> None:
    original = identity(target)
    source = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = tmp_path / "pyproject.toml"
    project.write_text(source.replace(f'version = "{original.version}"', 'version = "1.2.3"', 1), encoding="utf-8")
    upgraded = identity(target, project_file=project)
    assert upgraded.version == "1.2.3"
    assert upgraded.application_id == original.application_id
    assert upgraded.upgrade_code == original.upgrade_code
    assert UUID(original.upgrade_code).version == 5
    preview = identity(target, "preview")
    assert preview.upgrade_code != original.upgrade_code
    assert preview.application_id != original.application_id
    assert preview.package_name != original.package_name


def test_targets_share_application_identity_but_not_installer_families() -> None:
    values = [identity(item.name) for item in SUPPORTED_TARGETS]
    assert {item.application_id for item in values} == {"md.neve.cadrumo"}
    assert len({item.upgrade_code for item in values}) == len(values)
    assert [item.compatibility_floor for item in values] == [item.floor for item in SUPPORTED_TARGETS]


def test_published_windows_upgrade_code_cannot_drift() -> None:
    assert identity("windows-x86-64").upgrade_code == "9AA7A3AF-0C16-5672-8C22-1BA49EC0F757"


@pytest.mark.parametrize("target,channel", [("linux-i686", "stable"), ("macos-arm64", "../oops")])
def test_unknown_target_or_channel_is_rejected(target: str, channel: str) -> None:
    with pytest.raises(ValueError):
        identity(target, channel)


def test_cmake_metadata_is_literal() -> None:
    value = replace(identity("macos-arm64"), publisher='Publisher ${HOME}; "] =] ]=]')
    assert 'set(CADRUMO_ID_PUBLISHER [==[Publisher ${HOME}; "] =] ]=]]==])' in cmake_projection(value)
