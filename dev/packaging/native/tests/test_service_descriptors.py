"""The installed agent ceiling admits its hosted tools through the human session."""

import json
import re
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from cadrumo.adapters.persistence.storage.secure_object_namespaces import (
    EXTENSION_SETTINGS_NAMESPACE,
    LOCAL_MODEL_LIST_NAMESPACE,
)
from cadrumo_agent_service.providers.persistence.store import (
    LOCAL_MODEL_LIST_CAPABILITY,
    LOCAL_MODEL_LIST_KEY,
    PROVIDER_RECORD_CAPABILITY,
)
from cadrumo_client.contracts.service_access import InstalledServiceDescriptor

from ..service_descriptors import stage_service_descriptors

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _staged_service_descriptors(tmp_path: Path) -> tuple[InstalledServiceDescriptor, InstalledServiceDescriptor]:
    native = tmp_path / "bin"
    native.mkdir()
    for name in ("cadrumo-agent-service", "cadrumo-runtime"):
        (native / name).write_bytes(b"test image")
    layout = {
        "paths": {"native": "bin"},
        "entrypoint_suffix": "",
        "entrypoints": ["cadrumo-agent-service", "cadrumo-runtime"],
        "files": {"service_descriptors": "services.json"},
        "backend": "windows",
    }
    member = stage_service_descriptors(tmp_path, layout, ())
    service, holder = [
        InstalledServiceDescriptor.model_validate_json(json.dumps(item))
        for item in json.loads((tmp_path / member).read_bytes())
    ]
    return service, holder


def test_agent_descriptor_can_attend_tools_but_session_holder_cannot(tmp_path: Path) -> None:
    service, holder = _staged_service_descriptors(tmp_path)
    assert service.allow_descendants and service.operation_scope.allow_delegation
    assert service.operation_scope.operations
    assert not holder.allow_descendants and not holder.operation_scope.allow_delegation


def test_agent_descriptor_keeps_model_role_selections_in_their_own_registered_namespace(tmp_path: Path) -> None:
    """A selection must never share the provider records' namespace, whose generation binds the agent tree."""
    service, holder = _staged_service_descriptors(tmp_path)
    capabilities = {capability.capability: capability for capability in service.record_capabilities}

    for name, definition in (
        (PROVIDER_RECORD_CAPABILITY, EXTENSION_SETTINGS_NAMESPACE),
        (LOCAL_MODEL_LIST_CAPABILITY, LOCAL_MODEL_LIST_NAMESPACE),
    ):
        policy = capabilities[name]
        assert STORAGE_NAMESPACE_REGISTRY.namespace_by_value(policy.namespace) == definition
        assert policy.schema_version == definition.schema_version
        assert policy.classification is definition.sensitivity
        assert policy.actions == {"read", "write", "delete", "generation"}
    selections = capabilities[LOCAL_MODEL_LIST_CAPABILITY]
    assert selections.namespace != capabilities[PROVIDER_RECORD_CAPABILITY].namespace
    assert re.fullmatch(selections.key_pattern, LOCAL_MODEL_LIST_KEY) is not None
    assert re.fullmatch(selections.key_pattern, "example_api") is None
    # A provider record is keyed by its lane id: up to the agent's 64-character provider id and "_api".
    records = capabilities[PROVIDER_RECORD_CAPABILITY]
    for stored in ("example_api", "e" * 36 + "_cli", "e" * 64 + "_api"):
        assert re.fullmatch(records.key_pattern, stored) is not None
    assert re.fullmatch(records.key_pattern, "e" * 65 + "_api") is None
    assert holder.record_capabilities == ()
