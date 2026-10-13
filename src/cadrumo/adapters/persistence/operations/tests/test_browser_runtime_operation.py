"""The supervised browser provisioning operation over a real revision-pinned cache.

Every run goes through the real registry, supervisor, journal and encrypted
operand store. The cache is a real directory holding the builds the installed
Playwright pins; only the vendor download is an injected port, as production
composition injects it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....application.browser_runtime_operation import (
    BROWSER_RUNTIME_EXECUTE_PHASE,
    BROWSER_RUNTIME_OPERATION_DEFINITION_ID,
    BROWSER_RUNTIME_OPERATION_SUBJECT,
    BROWSER_RUNTIME_PREFLIGHT_PHASE,
    BROWSER_RUNTIME_SETTLEMENT_PHASE,
    BrowserRuntimeProvisionPublicResultV1,
)
from .....application.local_reader_contracts import local_reader_fact_mapping, local_reader_public_verdict
from .....application.provisioning_browser import BrowserBuild, required_browser_builds
from .....application.provisioning_contracts import ProvisioningPreconditionCondition
from .....application.tests.local_reader_operation_requests import build_browser_runtime_provision_request
from .....core.operations import OperationEffect
from .local_reader_operation_support import ProvisioningPorts, SupervisedRun, provisioning_registry, run_supervised

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


def _builds() -> tuple[BrowserBuild, ...]:
    builds = required_browser_builds()
    assert builds is not None, "the installed Playwright pins its Chromium builds"
    return builds


def _extract(cache: Path, build: BrowserBuild) -> None:
    (cache / build.directory_name).mkdir(parents=True)
    (cache / build.directory_name / "INSTALLATION_COMPLETE").write_bytes(b"")


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point browser provisioning at an empty cache of its own.

    The environment setting outranks every other source of the cache
    location, so it is the one that keeps a run off the host's real cache.
    """
    root = tmp_path / "browsers"
    root.mkdir()
    monkeypatch.setenv("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", str(root))
    return root


def _run(tmp_path: Path, ports: ProvisioningPorts) -> SupervisedRun[BrowserRuntimeProvisionPublicResultV1]:
    return run_supervised(
        tmp_path / "profile", ports, build_browser_runtime_provision_request(), BrowserRuntimeProvisionPublicResultV1
    )


def test_a_complete_cache_runs_no_download(tmp_path: Path, cache: Path) -> None:
    ports = ProvisioningPorts()
    for build in _builds():
        _extract(cache, build)
    run = _run(tmp_path, ports)

    assert run.result.installed is True
    assert run.result.already_installed is True
    assert run.result.installer_exit_code is None
    assert run.result.verdict_condition_id is None and run.result.verdict_facts == ()
    assert local_reader_fact_mapping(run.result.facts)["chromium_installed"] is True
    assert ports.browser_installs == 0
    assert run.effect is OperationEffect.NONE
    assert run.phases == (
        BROWSER_RUNTIME_PREFLIGHT_PHASE,
        BROWSER_RUNTIME_EXECUTE_PHASE,
        BROWSER_RUNTIME_SETTLEMENT_PHASE,
    )


def test_missing_builds_are_downloaded_and_confirmed_from_the_cache(tmp_path: Path, cache: Path) -> None:
    def download() -> int:
        for build in _builds():
            _extract(cache, build)
        return 0

    ports = ProvisioningPorts(browser_install=download)
    run = _run(tmp_path, ports)

    assert run.result.installed is True
    assert run.result.already_installed is False
    assert run.result.installer_exit_code == 0
    assert run.result.verdict_condition_id is None
    facts = local_reader_fact_mapping(run.result.facts)
    assert facts["installer_ran"] is True and facts["chromium_installed"] is True
    assert ports.browser_installs == 1
    assert run.effect is OperationEffect.UPDATED


def test_a_download_that_leaves_a_build_missing_is_refused_whatever_the_installer_reported(
    tmp_path: Path, cache: Path
) -> None:
    first, *_ = _builds()

    def download() -> int:
        _extract(cache, first)
        return 0

    ports = ProvisioningPorts(browser_install=download)
    run = _run(tmp_path, ports)

    assert run.result.installed is False
    assert run.result.already_installed is False
    assert run.result.installer_exit_code == 0
    verdict = local_reader_public_verdict(run.result.verdict_condition_id, run.result.verdict_facts)
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALL_SUCCEEDED
    facts = local_reader_fact_mapping(run.result.facts)
    assert facts["installer_ran"] is True and facts["chromium_installed"] is False
    assert first.directory_name not in str(facts["missing_builds"])
    assert run.effect is OperationEffect.PARTIAL, "one of the two builds stayed in the cache"


def test_the_operation_registers_with_the_browser_builds_fixed_subject() -> None:
    registry = provisioning_registry(ProvisioningPorts())
    definition = registry.lookup(BROWSER_RUNTIME_OPERATION_DEFINITION_ID)

    assert definition.subject_reference.literal == BROWSER_RUNTIME_OPERATION_SUBJECT == "browser-runtime:chromium"
    assert registry.lookup_public_contract(BROWSER_RUNTIME_OPERATION_DEFINITION_ID).result_schema is not None
