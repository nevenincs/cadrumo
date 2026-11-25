"""The console's provider homes are the ones the real cadrumo-agent seats its provider sign-in in.

The agent runs from the checkout ``CADRUMO_DEV_AGENT_CHECKOUT`` names. Its own
interpreter imports the agent's public layout and sign-in modules and runs this
package's ``provider_homes`` against them, as the bundled image's interpreter
does in process; beside it, the agent's own sign-in seats each provider's home,
which is the independent statement the console's homes must equal. The service
read then serves exactly those homes for a synthetic profile.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, cast
from uuid import uuid4

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_console_environment as console_module
from ...host.launch_environment import system_environment
from ...providers.domain.record import LocalEngine
from ...service import AgentService
from ..agent_process import WindowsAgentInvocationRunner
from ..agent_programs import profile_agent_root
from ..console_provisioning import CONSOLE_HOME_VARIABLES, LAYOUT_MODULE, SIGN_IN_MODULE

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external_tool,
    pytest.mark.windows_only,
    pytest.mark.hex_outbound_adapter,
]

CHECKOUT_VARIABLE: Final = "CADRUMO_DEV_AGENT_CHECKOUT"
_SOURCE_ROOT: Final = Path(__file__).resolve().parents[3]
"""The directory holding this package, which the agent's interpreter imports ``provider_homes`` from."""
_RENDER: Final = (
    "import json, shutil, sys, tempfile\n"
    "from pathlib import Path\n"
    "source, given = sys.argv[1], sys.argv[2]\n"
    "sys.path.insert(0, source)\n"
    f"import {LAYOUT_MODULE} as layout\n"
    f"import {SIGN_IN_MODULE} as sign_ins\n"
    "from cadrumo_agent_service.adapters.console_provisioning import CONSOLE_HOME_VARIABLES, provider_homes\n"
    "if given:\n"
    "    sys.stdout.write(json.dumps({'named': provider_homes(Path(given), layout=layout, sign_ins=sign_ins)}))\n"
    "    raise SystemExit(0)\n"
    # The agent seats no provider home inside a Git project, so its sign-in runs under a root outside one.
    "root = Path(tempfile.mkdtemp(prefix='cadrumo-console-homes-'))\n"
    "try:\n"
    "    seated = {sign_in.home_environment: sign_ins.hosted_provider_environment(name, root, {})[0]\n"
    "              for name, sign_in in sign_ins.PROVIDER_SIGN_INS.items()\n"
    "              if sign_in.home_environment in CONSOLE_HOME_VARIABLES}\n"
    "    named = provider_homes(root, layout=layout, sign_ins=sign_ins)\n"
    "    relative = lambda homes: {k: Path(v).relative_to(root).as_posix() for k, v in homes.items()}\n"
    "    sys.stdout.write(json.dumps({'named': relative(named), 'seated': relative(seated)}))\n"
    "finally:\n"
    "    shutil.rmtree(root)\n"
)


def _interpreter() -> Path:
    named = os.environ.get(CHECKOUT_VARIABLE)
    if named is None or not named.strip():
        pytest.fail(f"{CHECKOUT_VARIABLE} must name a synced cadrumo-agent checkout", pytrace=False)
    interpreter = Path(named) / ".venv" / "Scripts" / "python.exe"
    if not interpreter.is_file():
        pytest.fail(f"{CHECKOUT_VARIABLE} names no synced cadrumo-agent checkout", pytrace=False)
    return interpreter


def _agent_homes(agent_root: Path | None) -> dict[str, Any]:
    """The agent's homes under ``agent_root``; without one, its homes and sign-in seats under a fresh root."""
    interpreter = _interpreter()
    completed = WindowsAgentInvocationRunner().run(
        executable=interpreter,
        arguments=("-I", "-c", _RENDER, str(_SOURCE_ROOT), "" if agent_root is None else str(agent_root)),
        directory=interpreter.parent,
        environment=system_environment(os.environ),
        timeout=60.0,
        output_limit=64 * 1024,
    )
    assert completed.status == 0
    document = json.loads(completed.standard_output)
    assert isinstance(document, dict)
    return document


def test_the_console_homes_are_the_homes_the_agents_sign_in_seats() -> None:
    document = _agent_homes(None)

    assert set(document["named"]) == CONSOLE_HOME_VARIABLES
    assert document["named"] == document["seated"]
    assert len(set(document["named"].values())) == len(CONSOLE_HOME_VARIABLES)


def test_the_read_serves_the_agents_homes_for_the_signed_in_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console_module, "console_provider_homes", lambda root: _agent_homes(root)["named"])
    profile = uuid4()
    service = AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(
            InstalledServiceClient,
            SimpleNamespace(lease=SimpleNamespace(profile_id=profile), connection=SimpleNamespace(close=lambda: None)),
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )

    answer = service.admin("console_environment")

    agent_root = profile_agent_root(tmp_path, profile)
    assert answer["kind"] == "console_environment"
    assert answer["environment"] == _agent_homes(agent_root)["named"]
    assert set(answer["environment"]) == CONSOLE_HOME_VARIABLES
    for home in answer["environment"].values():
        assert Path(home).is_relative_to(agent_root)
