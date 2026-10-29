"""Keep the local AI server's fixed address equal in the package declaration, native contract and agent launch."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.core.config_runtime_fields import LOCAL_AI_SERVER_ADDRESS
from cadrumo_agent_service.host.launch_environment import OLLAMA_BASE_URL
from dev._paths import REPO_ROOT
from dev.packaging.native.application_environment import load, parse
from dev.packaging.native.environment_declaration_primitives import DECLARATION, ApplicationEnvironmentError
from dev.packaging.native.generate import generate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_declared_address_reaches_the_native_contract_and_the_agent_launch(tmp_path: Path) -> None:
    address = load(REPO_ROOT).components["local_ai_address"]
    generate(REPO_ROOT, tmp_path)
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    assert f'pub const LOCAL_AI_ADDRESS: &str = "{address}";' in generated
    assert address == LOCAL_AI_SERVER_ADDRESS
    assert f"http://{address}" == OLLAMA_BASE_URL


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1:11434",
        "127.0.0.1:80",
        "127.0.0.1:49152",
        "0.0.0.0:23743",
        "192.0.2.1:23743",
        "localhost:23743",
        "127.0.0.1",
    ],
)
def test_an_address_off_loopback_privileged_ephemeral_or_the_publishers_default_is_refused(address: str) -> None:
    text = (REPO_ROOT / DECLARATION).read_text(encoding="utf-8")
    declared = re.search(r'^local_ai_address = "[^"]*"$', text, flags=re.MULTILINE)
    assert declared is not None
    altered = text.replace(declared.group(0), f'local_ai_address = "{address}"')
    with pytest.raises(ApplicationEnvironmentError, match="local_ai_address"):
        parse(altered)
