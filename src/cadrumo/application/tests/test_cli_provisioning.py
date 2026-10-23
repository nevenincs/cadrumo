"""CLI startup reads published authority without loading its execution graph."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ...core.config import override_settings
from ...domain.calculations.registry.authority_location import (
    bundled_authority_descriptor_path,
    published_authority_generation,
)
from ...domain.calculations.registry.authority_store import AuthorityDescriptor, AuthorityStoreError
from ...domain.calculations.registry.errors import AuthorityDescriptorUnavailableError
from ..cli_provisioning import admit_cli_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_normal_authority_admission_retains_generation_and_log_fact_without_creating_storage(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    descriptor_path = bundled_authority_descriptor_path()
    descriptor = AuthorityDescriptor.read(descriptor_path)
    storage = tmp_path / "storage"
    caplog.set_level(logging.DEBUG, logger="cadrumo.application.cli_provisioning")

    with override_settings(cadrumo_authority_root=descriptor_path.parent, cadrumo_local_storage_root=storage):
        admit_cli_authority()
        assert published_authority_generation() == descriptor.logical_generation

    assert "CLI authority admitted" in caplog.messages
    assert not storage.exists()


@pytest.mark.parametrize("payload", [b"{}", b'{"format":"unexpected"}', b"not JSON"])
def test_malformed_authority_remains_a_refusal_without_materializing_storage(tmp_path: Path, payload: bytes) -> None:
    authority = tmp_path / "authority"
    authority.mkdir()
    (authority / "authority.current.json").write_bytes(payload)
    storage = tmp_path / "storage"

    with override_settings(cadrumo_authority_root=authority, cadrumo_local_storage_root=storage):
        with pytest.raises(AuthorityStoreError):
            admit_cli_authority()
        assert published_authority_generation() is None

    assert not storage.exists()


def test_absent_authority_is_not_provisioned_or_replaced_by_packaged_authority(tmp_path: Path) -> None:
    authority = tmp_path / "absent-authority"
    storage = tmp_path / "storage"

    with override_settings(cadrumo_authority_root=authority, cadrumo_local_storage_root=storage):
        with pytest.raises(AuthorityDescriptorUnavailableError) as refusal:
            admit_cli_authority()
        assert published_authority_generation() is None

    assert refusal.value.authority_root_configured is True
    assert refusal.value.searched_path == authority / "authority.current.json"
    assert not authority.exists()
    assert not storage.exists()
