"""Bind service admission policy to the final staged native image bytes."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cadrumo.application.operations.person_acts import operation_is_persons_act
from cadrumo.application.user_profile.access_contracts import AccessAction
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex

from .hashing import digest
from .layout import ApplicationImage, entrypoint_files


def stage_service_descriptors(root: Path, layout: dict[str, Any], images: tuple[ApplicationImage, ...]) -> str:
    """Write immutable policy only after relocation has fixed executable hashes."""
    from cadrumo.entrypoints.operation_composition import build_manifest_operation_registry

    entrypoints = entrypoint_files(layout)
    registry = build_manifest_operation_registry()
    operations = sorted(
        contract.definition_id
        for contract in registry.public_contract_set.definitions
        if not operation_is_persons_act(
            contract.definition_id, ephemeral_secret_required=contract.ephemeral_secret_required
        )
    )
    ceiling = {
        "operations": operations,
        "actions": sorted(action.value for action in AccessAction),
        "disclosures": [],
        "periods": None,
        "allow_period_independent": True,
        "allow_delegation": False,
        "allow_changes_records": True,
        "allow_network": True,
    }
    service: dict[str, Any] = {
        "service_id": "cadrumo-agent-service",
        "launch_image": entrypoints["cadrumo-agent-service"],
        "launch_module": "cadrumo_agent_service.main",
        "image_digest": digest(root / entrypoints["cadrumo-agent-service"]),
        "record_capabilities": [
            {
                "capability": "provider-settings",
                "namespace": "cadrumo.provider_settings",
                "schema_version": 1,
                "classification": "secret",
                "key_pattern": "^[a-z][a-z0-9_]{0,39}$",
                "maximum_bytes": 32768,
                "actions": ["read", "write", "delete", "generation"],
            }
        ],
        "operation_scope": ceiling,
        "allow_descendants": True,
        "allowed_parent_images": [],
    }
    parents = [
        {"launch_image": image.package_path, "image_digest": digest(root / image.package_path)}
        for image in images
        if image.desktop
    ]
    holder: dict[str, Any] = {
        "service_id": "desktop-session",
        "launch_image": entrypoints["cadrumo-runtime"],
        "launch_module": "cadrumo_runtime.host.bootstrap",
        "image_digest": digest(root / entrypoints["cadrumo-runtime"]),
        "record_capabilities": [],
        "operation_scope": dict(ceiling, operations=[], actions=[]),
        "allow_descendants": False,
        "allowed_parent_images": parents,
    }
    descriptors: list[Mapping[str, Any]] = []
    for descriptor in (service, holder):
        descriptor["descriptor_digest"] = sha256_hex(canonical_json_bytes(descriptor))
        descriptors.append(descriptor)
    relative = layout["files"]["service_descriptors"]
    if not isinstance(relative, str):
        raise TypeError("service descriptor member must be a string")
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(canonical_json_bytes(descriptors))
    return relative


def refresh_service_image_digests(root: Path, relative: str) -> None:
    """Preserve staged policy while rebinding a quiescent native image update."""
    path = root / relative
    descriptors = json.loads(path.read_bytes())
    if not isinstance(descriptors, list):
        raise ValueError("service descriptor inventory must be a list")
    for descriptor in descriptors:
        expected = descriptor.pop("descriptor_digest")
        if sha256_hex(canonical_json_bytes(descriptor)) != expected:
            raise ValueError("staged descriptor policy digest differs")
        members = [descriptor, *descriptor["allowed_parent_images"]]
        for member in members:
            image = root / member["launch_image"]
            if (
                not image.resolve(strict=True).is_relative_to(root.resolve(strict=True))
                or image.is_symlink()
                or image.is_junction()
            ):
                raise ValueError("staged descriptor image escapes the package")
            member["image_digest"] = digest(image)
        descriptor["descriptor_digest"] = sha256_hex(canonical_json_bytes(descriptor))
    path.write_bytes(canonical_json_bytes(descriptors))
