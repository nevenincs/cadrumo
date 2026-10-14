"""Profile workers retain tax authority without inheriting provider-service authority.

The real worker environment is inspected by an isolated child interpreter both
with and without an ambient agent executable. Retired tax/provider modules must
be absent, and importing the real profile worker must load no agent service.
Provider catalogue execution is covered by the service adapter's
adapters/tests/test_agent_provider_catalog.py; it is no longer a runtime worker duty.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo.core.type_guards import is_str_keyed_dict

from .. import profile_worker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="exercises the Windows worker environment filtering"),
]

_PACKAGE_AGENT_VARIABLE: Final = "CADRUMO_PACKAGE_AGENT_EXECUTABLE"
_RETIRED_MODULES: Final = (
    "cadrumo.adapters.persistence.provider_settings.store",
    "cadrumo.application.provider_settings.service",
    "cadrumo.domain.provider_settings.catalog",
    "cadrumo_client.transport.agent_programs",
    "cadrumo_client.transport.agent_provider_catalog",
)
_INSPECT_WORKER: Final = """\
import importlib.util
import json
import os
import sys
import cadrumo_runtime.adapters.profile_worker
unavailable = []
for name in json.loads(sys.argv[1]):
    try:
        spec = importlib.util.find_spec(name)
    except ModuleNotFoundError as error:
        if error.name is None or not (name == error.name or name.startswith(error.name + ".")):
            raise
        spec = None
    if spec is None:
        unavailable.append(name)
print(json.dumps({
    "agent_environment_present": "CADRUMO_PACKAGE_AGENT_EXECUTABLE" in os.environ,
    "retired_modules_absent": unavailable,
    "service_modules_loaded": sorted(name for name in sys.modules if name == "cadrumo_agent_service" or name.startswith("cadrumo_agent_service.")),
}))
"""


def _worker_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, image: Path | None) -> dict[str, str]:
    """Apply the real worker policy to an ambient frame, retaining no agent host location."""
    if image is None:
        monkeypatch.delenv(_PACKAGE_AGENT_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(_PACKAGE_AGENT_VARIABLE, str(image))
    root = tmp_path / "worker-storage"
    environment = profile_worker._worker_launch_environment(storage_root=root)
    # The worker delegates environment filtering to the declared shared policy.
    expected = child_environment(
        ChildEnvironmentProfile.OPERATOR,
        root,
        base=None if sys.platform == "win32" else {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        sys_platform=sys.platform,
    )
    assert environment == expected
    assert environment["CADRUMO_LOCAL_STORAGE_ROOT"] == str(root.resolve())
    return environment


async def _run_isolated(environment: dict[str, str], directory: Path) -> tuple[int | None, bytes, bytes]:
    """Run the real worker import in this interpreter's isolated package environment."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-B",
        "-c",
        _INSPECT_WORKER,
        json.dumps(_RETIRED_MODULES),
        env=environment,
        cwd=directory,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        standard_output, standard_error = await asyncio.wait_for(process.communicate(), 180)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    return process.returncode, standard_output, standard_error


def _observed_worker_boundary(environment: dict[str, str], directory: Path) -> dict[str, object]:
    status, standard_output, standard_error = asyncio.run(_run_isolated(environment, directory))
    assert status == 0, standard_error.decode(errors="replace")[-2000:]
    answer = json.loads(standard_output.decode().splitlines()[-1])
    assert is_str_keyed_dict(answer), answer
    return answer


def _require_no_provider_authority(environment: dict[str, str], directory: Path) -> None:
    assert _PACKAGE_AGENT_VARIABLE not in environment
    assert _observed_worker_boundary(environment, directory) == {
        "agent_environment_present": False,
        "retired_modules_absent": list(_RETIRED_MODULES),
        "service_modules_loaded": [],
    }


def test_a_worker_excludes_an_ambient_agent_location_and_provider_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ambient input is test data; no substitute agent or catalogue is launched.
    image = tmp_path / "ambient-agent.exe"
    environment = _worker_environment(tmp_path, monkeypatch, image)
    assert os.environ[_PACKAGE_AGENT_VARIABLE] == str(image)
    _require_no_provider_authority(environment, tmp_path)


def test_a_worker_without_an_agent_location_still_excludes_provider_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = _worker_environment(tmp_path, monkeypatch, None)
    assert _PACKAGE_AGENT_VARIABLE not in os.environ
    _require_no_provider_authority(environment, tmp_path)
