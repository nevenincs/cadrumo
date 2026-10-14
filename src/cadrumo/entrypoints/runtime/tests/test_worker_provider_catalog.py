"""A profile worker reaches the agent's provider catalog through the agent location the runtime relays.

The runtime's own image fixes the agent image's location. The worker runs the
provider-settings operations, which ask that agent for its catalog, so the
runtime relays the location into the worker's environment. Here the real
worker environment is composed from a runtime environment, and a real
interpreter started with exactly that environment asks a stand-in agent image
for its catalog, as a packaged worker does.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Final

import pytest

from ....adapters.local_runtime import profile_worker
from ....adapters.local_runtime.agent_programs import PACKAGE_AGENT_VARIABLE
from ....adapters.local_runtime.agent_provider_catalog import AgentProviderCatalogSource
from ....adapters.persistence.provider_settings.store import build_provider_settings_store
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.provider_settings.contracts import (
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
)
from ....application.provider_settings.service import ProviderSettingsService
from ....application.provider_settings.tests.synthetic_catalog import synthetic_document
from ....core.storage_environment import StorageMode
from ....domain.provider_settings.catalog import parse_provider_catalog
from .agent_host_support import stand_in_agent_image

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="the stand-in agent image is a Windows program"),
]

_BUCKET_ID: Final = "3a7c9e1f-5b2d-4c8e-9f60-1d2e3f4a5b6c"
# What the worker process does when a provider-settings operation needs the catalog.
_ASK_THE_AGENT: Final = """\
import json
from cadrumo.adapters.local_runtime.agent_provider_catalog import process_provider_catalog_source
from cadrumo.application.provider_settings.ports import ProviderCatalogUnavailableError
try:
    catalog = process_provider_catalog_source().catalog()
except ProviderCatalogUnavailableError as error:
    print(json.dumps({"unavailable": error.reason.value}))
else:
    print(json.dumps({"providers": sorted(catalog.provider_ids)}))
"""


def _worker_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, image: Path | None) -> dict[str, str]:
    """Compose the worker's environment from a runtime environment that does or does not name the agent."""
    if image is None:
        monkeypatch.delenv(PACKAGE_AGENT_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(PACKAGE_AGENT_VARIABLE, str(image))
    return profile_worker._worker_launch_environment(storage_root=tmp_path / "worker-storage")


async def _run_isolated(environment: dict[str, str], directory: Path) -> tuple[int | None, bytes, bytes]:
    """Run this interpreter isolated, as the worker runs, with exactly ``environment``."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-B",
        "-c",
        _ASK_THE_AGENT,
        env=environment,
        cwd=directory,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        standard_output, standard_error = await asyncio.wait_for(process.communicate(), 180)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    return process.returncode, standard_output, standard_error


def _asked_in_the_worker_environment(environment: dict[str, str], directory: Path) -> dict[str, object]:
    status, standard_output, standard_error = asyncio.run(_run_isolated(environment, directory))
    assert status == 0, standard_error.decode(errors="replace")[-2000:]
    answer: dict[str, object] = json.loads(standard_output.decode().splitlines()[-1])
    return answer


def _status(tmp_path: Path, environment: dict[str, str]) -> ProviderSettingsStatus | ProviderSettingsRefusal:
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_BUCKET_ID) as profile:
        service = ProviderSettingsService(
            store=build_provider_settings_store(bucket_id=profile.bucket_id, settings=profile.settings),
            catalog_source=AgentProviderCatalogSource(received=environment),
            environment={},
            storage_mode=StorageMode.INSTALLED,
        )
        return service.status()


def test_a_worker_given_the_runtimes_agent_location_reads_the_agents_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image, _record = stand_in_agent_image(tmp_path)
    environment = _worker_environment(tmp_path, monkeypatch, image)

    assert environment[PACKAGE_AGENT_VARIABLE] == str(image)
    expected = sorted(parse_provider_catalog(synthetic_document()).provider_ids)
    assert _asked_in_the_worker_environment(environment, tmp_path) == {"providers": expected}
    status = _status(tmp_path, environment)
    assert isinstance(status, ProviderSettingsStatus), status
    assert sorted(entry.id for entry in status.providers) == expected


def test_a_worker_without_an_agent_location_refuses_provider_status_as_catalog_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = _worker_environment(tmp_path, monkeypatch, None)

    assert PACKAGE_AGENT_VARIABLE not in environment
    assert _asked_in_the_worker_environment(environment, tmp_path) == {"unavailable": "agent_not_found"}
    status = _status(tmp_path, environment)
    assert isinstance(status, ProviderSettingsRefusal), status
    assert status.code is ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE
