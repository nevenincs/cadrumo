"""Every refusal code the service serves on the provider-settings path is one the desktop host admits.

The host keeps a closed refusal set and reports any other code as an unreadable
answer, so a code the service adds without the host would reach the person as
an unknown failure. This reads the host's own source, as the window's parity
checks read the Python contract.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ...providers.application.contracts import (
    ProviderSettingsRefusalCode,
    ServiceRefusalCode,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROOT = Path(__file__).resolve().parents[4]
_SERVICE = _ROOT / "src" / "cadrumo_agent_service"
_HOST = _ROOT / "native" / "desktop" / "src-tauri" / "src" / "shell" / "provider_settings"


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _host_refusals() -> set[str]:
    source = (_HOST / "wire.rs").read_text(encoding="utf-8")
    block = re.search(r"pub enum Refusal \{(.*?)\n\}", source, re.DOTALL)
    assert block is not None
    return {_snake(name) for name in re.findall(r"^\s*([A-Z]\w*),", block.group(1), re.MULTILINE)}


def _host_renames() -> dict[str, str]:
    source = (_HOST / "mod.rs").read_text(encoding="utf-8")
    body = source[source.index("pub(crate) fn outcome(") :]
    body = body[: body.index("\n}\n")]
    return dict(re.findall(r'"(\w+)" => "(\w+)"', body))


def _served_codes() -> set[str]:
    codes = {code.value for code in ProviderSettingsRefusalCode}
    for module in ("service_administration.py", "service_startup.py"):
        source = (_SERVICE / module).read_text(encoding="utf-8")
        codes |= set(re.findall(r'refuse\(\s*"(\w+)"', source))
        codes |= {
            ServiceRefusalCode[name].value for name in re.findall(r"refuse\(\s*ServiceRefusalCode\.(\w+)", source)
        }
        codes |= set(re.findall(r'"kind": "refused", "code": "(\w+)"', source))
    return codes


def test_every_served_refusal_code_is_admitted_by_the_host() -> None:
    admitted = _host_refusals()
    renames = _host_renames()
    served = _served_codes()
    assert {"busy", "signed_out", "invalid_request", "service_failed"} <= served
    missing = sorted(code for code in served if renames.get(code, code) not in admitted)
    assert not missing, missing


def test_the_service_codes_are_declared_and_their_host_names_are_the_hosts_own() -> None:
    renames = _host_renames()
    declared = {code.value for code in ServiceRefusalCode}
    served = _served_codes() - {code.value for code in ProviderSettingsRefusalCode}
    assert served <= declared, sorted(served - declared)
    assert set(renames) <= declared, sorted(set(renames) - declared)


def test_every_code_the_host_admits_is_a_declared_settings_or_service_code() -> None:
    relayed = {code.value for code in ProviderSettingsRefusalCode} | {
        _host_renames().get(code.value, code.value) for code in ServiceRefusalCode
    }
    assert relayed == _host_refusals()
