"""Explicit binary selection for process lifecycle acceptance."""

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from cadrumo.core.config import override_settings
from cadrumo.core.storage_environment import STORAGE_ROOT

from ..harness import LifecycleHarness
from .evidence import manager_evidence, runtime_faults


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("runtime lifecycle")
    group.addoption("--lifecycle-manager", type=Path, help="Debug manager lifecycle driver image")
    group.addoption("--lifecycle-package", type=Path, help="Complete real native package directory")


@pytest.fixture
def lifecycle_binaries(pytestconfig: pytest.Config) -> tuple[Path, Path]:
    manager = pytestconfig.getoption("lifecycle_manager")
    package = pytestconfig.getoption("lifecycle_package")
    if not isinstance(manager, Path) or not isinstance(package, Path):
        pytest.fail("Supply --lifecycle-manager and --lifecycle-package; see dev/runtime_lifecycle/README.md")
    return manager.resolve(strict=True), package.resolve(strict=True)


@pytest.fixture
def harness(
    lifecycle_binaries: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, record_property: Any
) -> Iterator[LifecycleHarness]:
    manager, package = lifecycle_binaries
    root = tmp_path / "storage"
    monkeypatch.setenv(STORAGE_ROOT.variable, str(root))
    monkeypatch.setenv(STORAGE_ROOT.development_variable, str(root))
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(package / "data/authority"))
    instance = LifecycleHarness(manager, package, root)
    try:
        with (
            override_settings(
                cadrumo_local_storage_root=root,
                cadrumo_authority_root=package / "data/authority",
            ),
            instance,
        ):
            probe = instance.connect(uuid4())
            instance.metrics["startup_seconds"] = time.monotonic() - instance.started
            probe.client.close()
            yield instance
    finally:
        record_property("lifecycle_seconds", json.dumps(instance.metrics, sort_keys=True))
        record_property("manager_events", json.dumps(manager_evidence(root / "manager-events.jsonl"), sort_keys=True))
        record_property("runtime_faults", json.dumps(runtime_faults(root / "logs/cadrumo.log")))
        if not instance.events():
            raise RuntimeError("Native lifecycle driver did not retain any public supervision evidence")
