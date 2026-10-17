"""Provision the actual runtime, profile and service once for this suite."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.core.storage_environment import prepare_temporary_directory
from dev.agent_eval.live.package_copy import verify_package

from ...agent_service_session import AgentServiceSession, agent_service_session


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("agent service")
    group.addoption(
        "--agent-provider-cli", default="claude", help="Installed provider executable for the service suite"
    )


@pytest.fixture(scope="package")
def agent_service(pytestconfig: pytest.Config) -> Iterator[AgentServiceSession]:
    """Share one sign-in within this suite, then close it before sibling suites."""
    if hasattr(pytestconfig, "workerinput"):
        pytest.fail("Run the shared agent-service suite with -n 0; it owns one bootstrap for the entire suite")
    package = pytestconfig.getoption("lifecycle_package")
    if not isinstance(package, Path):
        pytest.fail("The agent-service suite requires --lifecycle-package naming the verified application directory")
    external = tuple(
        Path(value) for value in os.environ.get("CADRUMO_EXTERNAL_BIN_DIRS", "").split(os.pathsep) if value
    )
    if not external:
        executable = shutil.which(pytestconfig.getoption("agent_provider_cli"))
        if executable is None:
            pytest.fail("The selected provider CLI is not installed; supply --agent-provider-cli")
        external = (Path(executable).resolve(strict=True).parent,)
    base = prepare_temporary_directory()
    started = time.monotonic()
    verified = verify_package(package.resolve(strict=True))
    print("agent suite package:", verified.manifest_digest, verified.file_count, flush=True)
    with (
        tempfile.TemporaryDirectory(prefix="cadrumo-agent-suite-", dir=base) as directory,
        agent_service_session(package.resolve(strict=True), Path(directory), external_bin_dirs=external) as session,
    ):
        print("agent suite setup:", json.dumps(session.setup_counts, sort_keys=True), flush=True)
        print("agent suite bootstrap seconds:", round(time.monotonic() - started, 3), flush=True)
        print("agent suite setup timings:", json.dumps(session.timings, sort_keys=True), flush=True)
        print("agent suite CLI sign-in persisted:", session.login_session_persisted, flush=True)
        print("agent suite agent event:", json.dumps(session.agent_event, sort_keys=True), flush=True)
        print("agent suite refusal:", session.first_refusal_code, session.native_refusal_codes, flush=True)
        yield session
        assert all(count == 1 for count in session.setup_counts.values())
        print("agent suite reused:", json.dumps(session.setup_counts, sort_keys=True), flush=True)
