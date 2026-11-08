"""A hosted agent that fails its setup before ready is published as a refusal, never as an exit.

The agent is the real gateway of the checkout ``CADRUMO_DEV_AGENT_CHECKOUT``
names, started inside the service's own kill-on-close job on a set-up hosted
root, with its MCP SDK made unimportable the way the agent's own refusal test
does it. The agent then exits with its start-up refusal status after writing
its refused line on standard output and a coded line naming the import error
last on standard error.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Final

import pytest

from cadrumo.tests.log_records import delivered_records

from ...adapters.agent_process import WindowsAgentInvocationRunner, WindowsAgentProcessLauncher
from ...adapters.agent_programs import AGENT_COMMAND_LINE
from ...service_support import service_failure
from ..controller import (
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentHostState,
    AgentLaunch,
)
from ..launch_environment import (
    GATEWAY_PORT_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    WORKER_PORT_VARIABLE,
    system_environment,
)
from .agent_checkout_support import FixedCredentials, agent_checkout, checkout_interpreter

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external_tool,
    pytest.mark.windows_only,
    pytest.mark.hex_application,
]

_SERVE_WITHOUT_MCP: Final = (
    'import sys; sys.modules["mcp"] = None; from cadrumo_agent.cli.main import main; main(["serve"])'
)
_IMPORT_ERROR: Final = "import of mcp halted"


def test_a_start_whose_setup_fails_before_ready_is_a_refused_event_with_the_reason_kept_out_of_it(
    outside_git_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    interpreter = checkout_interpreter(agent_checkout())
    root = outside_git_path / "profile"
    root.mkdir()
    environment = system_environment(os.environ) | {HOSTED_ROOT_VARIABLE: str(root)}
    setup = WindowsAgentInvocationRunner().run(
        executable=interpreter,
        arguments=(*AGENT_COMMAND_LINE, "setup"),
        directory=root,
        environment=environment,
        timeout=120,
        output_limit=64 * 1024,
    )
    assert setup.status == 0, setup.standard_output[-2000:]
    controller = AgentHostController(
        launcher=WindowsAgentProcessLauncher(),
        credentials=FixedCredentials(),
        launch=AgentLaunch(
            executable=interpreter,
            arguments=("-c", _SERVE_WITHOUT_MCP),
            directory=root,
            environment=environment | {GATEWAY_PORT_VARIABLE: "0", WORKER_PORT_VARIABLE: "0"},
        ),
    )

    with caplog.at_level(logging.DEBUG, logger="cadrumo_agent_service.service"):
        with pytest.raises(AgentHostError) as refused:
            controller.start()
        event = service_failure(refused.value)

    # The agent's own refused line, read as the agent's code, not as a tree that merely ended.
    assert refused.value.reason is AgentHostRefusal.AGENT_REFUSED
    assert refused.value.agent_code == "hosted_start_failed"
    assert controller.state is AgentHostState.DETACHED
    # What the desktop is sent: the launcher protocol's closed code for a failure to serve.
    assert event == {"event": "refused", "code": "agent_service_failed"}
    assert _IMPORT_ERROR not in json.dumps(event)
    # The service's own log names the agent's code, and only its own log.
    assert any(
        "agent_code=hosted_start_failed" in record.getMessage()
        for record in delivered_records(caplog)
        if record.name == "cadrumo_agent_service.service"
    )
