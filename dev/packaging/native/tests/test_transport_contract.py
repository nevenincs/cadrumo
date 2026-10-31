"""Generated transport policy and manager identities stay anchored in core."""

from __future__ import annotations

import pytest

from cadrumo.core.connection_transport import manager_socket_name, root_scoped_identifier

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
    assert 'pub const INSTANCE_ROOT_SCOPE: &str = ".root.";' in rust
    assert "pub const INSTANCE_SCOPE_VECTORS: &[InstanceScopeVector]" in rust
    for vector in (*section["manager_vectors"], *section["instance_scope_vectors"]):
        for value in vector.values():
            assert value in rust


def test_root_scope_keeps_roots_and_channels_apart_and_feeds_the_manager_name() -> None:
    root = "0" * 63 + "1"
    assert root_scoped_identifier("md.neve.cadrumo", root) == f"md.neve.cadrumo.root.{root}"
    section = transport_section()
    scoped = {vector["expected_identifier"] for vector in section["instance_scope_vectors"]}
    assert len(scoped) == len(section["instance_scope_vectors"]) >= 6
    # Two roots of one manager in one session name two manager sockets.
    names = {vector["expected_name"] for vector in section["manager_vectors"] if ".root." in vector["manager_id"]}
    assert len(names) == 2
    assert manager_socket_name("md.neve.cadrumo.manager", "501", "100008") not in names


@pytest.mark.parametrize("identity", ["", "0" * 63, "0" * 65, "A" * 64, "g" * 64, " " + "0" * 63, "\u0660" * 64])
def test_root_scope_refuses_a_malformed_storage_identity(identity: str) -> None:
    with pytest.raises(ValueError):
        root_scoped_identifier("md.neve.cadrumo", identity)


@pytest.mark.parametrize("identifier", ["", ".id", "id.", "id/x", "mé", "a" * 59])
def test_root_scope_refuses_identifiers_it_cannot_bound(identifier: str) -> None:
    with pytest.raises(ValueError):
        root_scoped_identifier(identifier, "f" * 64)
    assert root_scoped_identifier("a" * 58, "f" * 64).endswith("f" * 64)


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
