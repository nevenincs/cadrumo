"""The installed agent ceiling admits its hosted tools through the human session."""

import json
from pathlib import Path

import pytest

from cadrumo_client.contracts.service_access import InstalledServiceDescriptor

from ..service_descriptors import stage_service_descriptors

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_agent_descriptor_can_attend_tools_but_session_holder_cannot(tmp_path: Path) -> None:
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
    assert service.allow_descendants and service.operation_scope.allow_delegation
    assert service.operation_scope.operations
    assert not holder.allow_descendants and not holder.operation_scope.allow_delegation
