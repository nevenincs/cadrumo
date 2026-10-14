"""The adapter that obtains the provider catalog from cadrumo-agent, run through the real parser."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import override

import pytest

from ....application.agent_host.controller import AgentHostError, AgentHostRefusal
from ....application.agent_host.store_lifecycle import AgentInvocationResult, AgentInvocationRunner
from ....application.provider_settings.ports import ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason
from ....application.provider_settings.tests.synthetic_catalog import KEY_LANE, synthetic_document
from ..agent_process import WindowsAgentInvocationRunner
from ..agent_programs import PACKAGE_AGENT_VARIABLE
from ..agent_provider_catalog import CATALOG_ARGUMENTS, AgentProviderCatalogSource

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _Runner(AgentInvocationRunner):
    def __init__(self, result: AgentInvocationResult | Exception) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    @override
    def run(
        self,
        *,
        executable: Path,
        arguments: Sequence[str],
        directory: Path,
        environment: Mapping[str, str],
        timeout: float,
        output_limit: int,
    ) -> AgentInvocationResult:
        self.calls.append({"executable": executable, "arguments": tuple(arguments), "environment": dict(environment)})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _image(tmp_path: Path) -> Path:
    image = tmp_path / "cadrumo-agent.exe"
    image.write_bytes(b"")
    return image


def _source(tmp_path: Path, result: AgentInvocationResult | Exception) -> tuple[AgentProviderCatalogSource, _Runner]:
    runner = _Runner(result)
    environment = {
        PACKAGE_AGENT_VARIABLE: str(_image(tmp_path)),
        "SYSTEMROOT": r"C:\Windows",
        "CADRUMO_LLM_X_API_KEY": "k",
    }
    return AgentProviderCatalogSource(received=environment, runner=runner), runner


def _ok(document: str) -> AgentInvocationResult:
    return AgentInvocationResult(status=0, standard_output=document.encode())


def test_the_agent_is_asked_for_its_offline_declaration_in_a_credential_free_environment(tmp_path: Path) -> None:
    source, runner = _source(tmp_path, _ok(synthetic_document()))

    catalog = source.catalog()
    again = source.catalog()

    assert catalog.entry(KEY_LANE) is not None
    assert again is catalog
    assert len(runner.calls) == 1
    call = runner.calls[0]
    assert call["arguments"] == ("-m", "cadrumo_agent.cli.main", "providers", "--declared", "--json")
    assert call["arguments"] == CATALOG_ARGUMENTS
    assert "CADRUMO_LLM_X_API_KEY" not in json.dumps(call["environment"])


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        pytest.param(
            AgentInvocationResult(status=1, standard_output=b""), ProviderCatalogUnavailableReason.AGENT_FAILED
        ),
        pytest.param(
            AgentInvocationResult(status=None, standard_output=b""), ProviderCatalogUnavailableReason.AGENT_TIMED_OUT
        ),
        pytest.param(AgentHostError(AgentHostRefusal.LAUNCH_FAILED), ProviderCatalogUnavailableReason.AGENT_FAILED),
        pytest.param(OSError("denied"), ProviderCatalogUnavailableReason.AGENT_FAILED),
        pytest.param(_ok("not json"), ProviderCatalogUnavailableReason.CATALOG_MALFORMED),
        pytest.param(
            _ok(json.dumps({"schema_version": 2, "providers": json.loads(synthetic_document())["providers"]})),
            ProviderCatalogUnavailableReason.CATALOG_MALFORMED,
        ),
        pytest.param(
            AgentInvocationResult(status=0, standard_output=b"x" * (256 * 1024 + 1)),
            ProviderCatalogUnavailableReason.CATALOG_MALFORMED,
        ),
        pytest.param(
            AgentInvocationResult(status=0, standard_output=b"\xff\xfe"),
            ProviderCatalogUnavailableReason.CATALOG_MALFORMED,
        ),
    ],
)
def test_every_failure_is_a_typed_refusal_and_is_never_cached(
    tmp_path: Path, result: AgentInvocationResult | Exception, reason: ProviderCatalogUnavailableReason
) -> None:
    source, runner = _source(tmp_path, result)

    with pytest.raises(ProviderCatalogUnavailableError) as refused:
        source.catalog()
    runner.result = _ok(synthetic_document())

    assert refused.value.reason is reason
    assert source.catalog().entry(KEY_LANE) is not None


def test_no_located_agent_is_a_typed_refusal(tmp_path: Path) -> None:
    runner = _Runner(_ok(synthetic_document()))
    source = AgentProviderCatalogSource(received={"SYSTEMROOT": r"C:\Windows"}, runner=runner)

    with pytest.raises(ProviderCatalogUnavailableError) as refused:
        source.catalog()

    assert refused.value.reason is ProviderCatalogUnavailableReason.AGENT_NOT_FOUND
    assert runner.calls == []


def test_the_default_runner_is_the_runtime_s_contained_invocation_runner() -> None:
    source = AgentProviderCatalogSource(received={})

    assert isinstance(source._runner, WindowsAgentInvocationRunner)
