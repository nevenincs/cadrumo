"""``config provision status``, ``probe`` and ``report`` answer when the runtime cannot be reached.

Each reads the model runtime over HTTP at the configured endpoint, which defaults
to this machine's loopback interface and may name a remote host, so each declares
``network``. ``probe`` also loads the text model on that runtime, so it alone
declares the network side effect; ``status`` stays side-effect-free. With the
process sealed offline each must still answer, reporting the runtime as
unreachable as a state rather than crashing or refusing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest

from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.provisioning_runtime import forget_runtime_unreachable
from ....core.config import override_settings
from ....tests.cli_envelope import require_schema_envelope
from ....tests.offline_seal import OfflineGuard, offline_guard_fixture
from ..command_specs import COMMAND_GRAPH
from .cli_runner import invoke_cached_cli

__all__ = ["offline_guard_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_ENDPOINTS: Final = {
    "loopback": "http://127.0.0.1:11434/api/chat",
    "remote": "http://model-runtime.offline-probe.invalid:11434/api/chat",
}


@pytest.mark.parametrize("key", ["config_provision_status", "config_provision_probe", "config_provision_report"])
def test_a_runtime_reading_provision_command_declares_network(key: str) -> None:
    assert "network" in COMMAND_GRAPH.spec(key).policy.expanded_capabilities


def test_only_probe_declares_the_model_load_it_causes() -> None:
    status = COMMAND_GRAPH.spec("config_provision_status")
    probe = COMMAND_GRAPH.spec("config_provision_probe")

    assert status.policy.side_effects == frozenset({"none"})
    assert status.parameters == ()
    assert "network" in probe.policy.side_effects


def _run_offline(tmp_path: Path, endpoint: str, *command: str) -> tuple[int, dict[str, Any]]:
    with isolated_profile_storage_root(tmp_path=tmp_path), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        forget_runtime_unreachable()
        result = invoke_cached_cli(["--format", "json", "config", "provision", *command])
    return result.exit_code, require_schema_envelope(result.stdout)


@pytest.mark.parametrize("command", ["status", "probe"])
@pytest.mark.parametrize("endpoint", list(_ENDPOINTS))
def test_status_reports_an_unreachable_runtime_offline(
    command: str,
    endpoint: str,
    tmp_path: Path,
    offline_guard: OfflineGuard,
) -> None:
    exit_code, result = _run_offline(tmp_path, _ENDPOINTS[endpoint], command)

    assert exit_code == 0, result
    runtime = result["runtime"]
    assert isinstance(runtime, dict)
    assert runtime["reachable"] is False
    assert runtime["version"] is None
    assert runtime["endpoint_local"] is (endpoint == "loopback")
    assert result["extraction_ready"] is False
    assert offline_guard.refused, f"{command} never tried the runtime endpoint"


@pytest.mark.parametrize("endpoint", list(_ENDPOINTS))
def test_report_reports_an_unreachable_runtime_offline(
    endpoint: str,
    tmp_path: Path,
    offline_guard: OfflineGuard,
) -> None:
    exit_code, result = _run_offline(tmp_path, _ENDPOINTS[endpoint], "report")

    assert exit_code == 0, result
    assert result["runtime_reachable"] is False
    assert result["residents"] == []
    assert offline_guard.refused, "the report never tried the runtime endpoint"
