"""Keep each local AI server's fixed address equal in the package declaration, native contract and agent launch."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.core.config_runtime_fields import LOCAL_AI_SERVER_ADDRESS
from cadrumo_agent_service.host.launch_environment import OLLAMA_BASE_URL
from dev.env.llamacpp_pins import load_server_pins
from dev.packaging.native.application_environment import load, parse
from dev.packaging.native.environment_declaration_primitives import DECLARATION, ApplicationEnvironmentError
from dev.packaging.native.generate import generate
from dev.paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_declared_addresses_reach_the_native_contract_and_the_agent_launch(tmp_path: Path) -> None:
    components = load(REPO_ROOT).components
    address, llama_server = components["local_ai_address"], components["llama_server_address"]
    generate(REPO_ROOT, tmp_path)
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    assert f'pub const LOCAL_AI_ADDRESS: &str = "{address}";' in generated
    assert f'pub const LLAMA_SERVER_ADDRESS: &str = "{llama_server}";' in generated
    assert llama_server != address
    assert address == LOCAL_AI_SERVER_ADDRESS
    assert f"http://{address}" == OLLAMA_BASE_URL


def test_the_native_contract_names_the_pinned_llama_server_build(tmp_path: Path) -> None:
    generate(REPO_ROOT, tmp_path)
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    tag = load_server_pins().tag
    assert re.fullmatch(r"b[0-9]+", tag)
    assert f'pub const LLAMA_SERVER_BUILD: &str = "{tag}";' in generated


def _declared_with(key: str, address: str) -> str:
    text = (REPO_ROOT / DECLARATION).read_text(encoding="utf-8")
    declared = re.search(rf'^{key} = "[^"]*"$', text, flags=re.MULTILINE)
    assert declared is not None
    return text.replace(declared.group(0), f'{key} = "{address}"')


@pytest.mark.parametrize("key", ["local_ai_address", "llama_server_address"])
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
def test_an_address_off_loopback_privileged_ephemeral_or_the_publishers_default_is_refused(
    key: str, address: str
) -> None:
    with pytest.raises(ApplicationEnvironmentError, match=key):
        parse(_declared_with(key, address))


def test_the_two_servers_never_share_an_address() -> None:
    shared = load(REPO_ROOT).components["local_ai_address"]
    with pytest.raises(ApplicationEnvironmentError, match="llama_server_address must differ"):
        parse(_declared_with("llama_server_address", shared))
