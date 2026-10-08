"""Project the canonical transient transport declaration and naming vectors."""

from __future__ import annotations

import json
from typing import Any

from cadrumo.core import runtime_transport as declaration
from cadrumo.core.product_identity import PRODUCT_IDENTITY


def transport_section() -> dict[str, Any]:
    """Return platform-neutral declarations, without consulting the build host."""
    coordinates = (
        (f"{PRODUCT_IDENTITY.application_id}.manager", "501", "100008"),
        (f"{PRODUCT_IDENTITY.application_id}.preview.manager", "501", "100008"),
        (f"{PRODUCT_IDENTITY.application_id}.manager", "502", "100008"),
        (f"{PRODUCT_IDENTITY.application_id}.manager", "501", "100009"),
    )
    return {
        "darwin_directory": PRODUCT_IDENTITY.python_package,
        "path_limit": declaration.RUNTIME_SOCKET_PATH_LIMIT,
        "manager_domain": declaration.MANAGER_SOCKET_DOMAIN,
        "manager_prefix": declaration.MANAGER_SOCKET_PREFIX,
        "manager_suffix": declaration.MANAGER_SOCKET_SUFFIX,
        "manager_digest_bytes": declaration.MANAGER_SOCKET_DIGEST_BYTES,
        "manager_max_identifier_bytes": declaration.MANAGER_SOCKET_MAX_IDENTIFIER_BYTES,
        "manager_vectors": [
            {
                "manager_id": manager,
                "user": user,
                "session": session,
                "expected_name": declaration.manager_socket_name(manager, user, session),
            }
            for manager, user, session in coordinates
        ],
    }


def rust_transport(section: dict[str, Any]) -> list[str]:
    """Emit Rust consumers and immutable cross-language filename fixtures."""
    strings = {
        "DARWIN_RUNTIME_SOCKET_DIRECTORY": "darwin_directory",
        "MANAGER_SOCKET_DOMAIN": "manager_domain",
        "MANAGER_SOCKET_PREFIX": "manager_prefix",
        "MANAGER_SOCKET_SUFFIX": "manager_suffix",
    }
    lines = [f"pub const {name}: &str = {json.dumps(section[key])};" for name, key in strings.items()]
    lines.extend(
        [
            f"pub const RUNTIME_SOCKET_PATH_LIMIT: usize = {section['path_limit']};",
            f"pub const MANAGER_SOCKET_DIGEST_BYTES: usize = {section['manager_digest_bytes']};",
            f"pub const MANAGER_SOCKET_MAX_IDENTIFIER_BYTES: usize = {section['manager_max_identifier_bytes']};",
            "pub struct ManagerSocketVector { pub manager_id: &'static str, pub user: &'static str, "
            "pub session: &'static str, pub expected_name: &'static str }",
            "pub const MANAGER_SOCKET_VECTORS: &[ManagerSocketVector] = &[",
        ]
    )
    for vector in section["manager_vectors"]:
        fields = ", ".join(f"{key}: {json.dumps(value)}" for key, value in vector.items())
        lines.append(f"ManagerSocketVector {{ {fields} }},")
    lines.append("];")
    return lines
