"""Real concurrent metadata publication and fail-closed installation binding."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from ..installation import read_runtime_installation, runtime_installation

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]


def test_racing_installation_reads_converge_without_an_os_secret_store(tmp_path: Path) -> None:
    def read():
        return runtime_installation(storage_root=tmp_path, os_owner_id="synthetic-owner", storage_identity="a" * 64)

    with ThreadPoolExecutor(max_workers=8) as pool:
        identities = tuple(future.result() for future in [pool.submit(read) for _ in range(12)])
    assert all(item == identities[0] for item in identities)
    assert read() == identities[0]
    assert (
        read_runtime_installation(storage_root=tmp_path, os_owner_id="synthetic-owner", storage_identity="a" * 64)
        == identities[0]
    )
    before = (tmp_path / ".runtime" / "installation.json").read_bytes()
    for owner, root in (("another-owner", "a" * 64), ("synthetic-owner", "b" * 64)):
        with pytest.raises(RuntimeRefusalError) as refused:
            runtime_installation(storage_root=tmp_path, os_owner_id=owner, storage_identity=root)
        assert refused.value.reason is RuntimeRefusalCode.ROOT_MISMATCH
    assert (tmp_path / ".runtime" / "installation.json").read_bytes() == before


def test_passive_identity_read_never_creates_a_missing_installation(tmp_path: Path) -> None:
    with pytest.raises(RuntimeRefusalError):
        read_runtime_installation(storage_root=tmp_path, os_owner_id="synthetic-owner", storage_identity="a" * 64)
    assert tuple(tmp_path.iterdir()) == ()
    directory = tmp_path / ".runtime"
    directory.mkdir()
    with pytest.raises(RuntimeRefusalError) as refused:
        read_runtime_installation(storage_root=tmp_path, os_owner_id="synthetic-owner", storage_identity="a" * 64)
    assert refused.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert tuple(directory.iterdir()) == ()


@pytest.mark.parametrize(
    "invalid",
    [b"not-json", b'{"version":1,"version":1}', b"{}", b"x" * 4097],
    ids=("invalid-json", "duplicate-member", "missing-fields", "oversized"),
)
def test_corrupt_identity_is_not_replaced_with_a_new_installation(tmp_path: Path, invalid: bytes) -> None:
    directory = tmp_path / ".runtime"
    directory.mkdir()
    path = directory / "installation.json"
    path.write_bytes(invalid)
    with pytest.raises(RuntimeRefusalError):
        runtime_installation(storage_root=tmp_path, os_owner_id="synthetic-owner", storage_identity="a" * 64)
    assert path.read_bytes() == invalid
