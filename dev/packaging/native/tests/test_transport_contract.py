"""Generated transport policy and manager identities stay anchored in core."""

from __future__ import annotations

import pytest

from cadrumo.core.runtime_transport import manager_socket_name

from ..transport_contract import rust_transport, transport_section

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_compact_manager_vector_and_coordinate_separation() -> None:
    assert manager_socket_name("md.neve.cadrumo.manager", "501", "100008") == "manager-EvXnxqYH34jLg0wtHSXzQw.sock"
    vectors = transport_section()["manager_vectors"]
    assert len({vector["expected_name"] for vector in vectors}) == len(vectors)
    assert all(len(vector["expected_name"]) == 35 for vector in vectors)


def test_projection_has_declared_transport_names_and_complete_vectors() -> None:
    section = transport_section()
    assert section["darwin_directory"] == "cadrumo"
    assert section["path_limit"] == 104
    rust = "\n".join(rust_transport(section))
    assert 'pub const MANAGER_SOCKET_DOMAIN: &str = "cadrumo-manager-session-v1";' in rust
    assert 'pub const MANAGER_SOCKET_PREFIX: &str = "manager-";' in rust
    assert 'pub const MANAGER_SOCKET_SUFFIX: &str = ".sock";' in rust
    assert "pub const MANAGER_SOCKET_DIGEST_BYTES: usize = 16;" in rust
    assert "pub const MANAGER_SOCKET_VECTORS: &[ManagerSocketVector]" in rust
    for vector in section["manager_vectors"]:
        for value in vector.values():
            assert value in rust


@pytest.mark.parametrize("coordinate", ["", "01", "+1", "-1", "4294967296", " 1", "1/2", "\u0661"])
def test_manager_coordinates_refuse_noncanonical_native_values(coordinate: str) -> None:
    with pytest.raises(ValueError):
        manager_socket_name("md.neve.cadrumo.manager", coordinate, "501")
    with pytest.raises(ValueError):
        manager_socket_name("md.neve.cadrumo.manager", "501", coordinate)


@pytest.mark.parametrize("identifier", ["", ".id", "id.", "id/manager", "id manager", "mé", "a" * 129])
def test_manager_identifier_refuses_unbounded_or_non_ascii_names(identifier: str) -> None:
    with pytest.raises(ValueError):
        manager_socket_name(identifier, "501", "100008")


def test_native_coordinate_bounds_are_valid() -> None:
    assert manager_socket_name("a" * 128, "0", "4294967295").endswith(".sock")
