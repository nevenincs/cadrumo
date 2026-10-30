"""Repository-owned installed runtime setup for product-owner process tests."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from pathlib import Path

import pytest

from cadrumo.tests.installed_process_ports import InstalledProcessWorld
from dev.acceptance.installed_cli import build_installed_cli_environment
from dev.packaging.installed_runtime import installed_cli_runtime


class RepositoryInstalledProcessWorld:
    """Keep the existing real installed runtime and clean environment implementations."""

    def environment(self, *, storage_root: Path, authority_root: Path) -> dict[str, str]:
        return build_installed_cli_environment(storage_root=storage_root, authority_root=authority_root)

    def runtime(self, cli: Path, environment: Mapping[str, str], log: Path) -> AbstractContextManager[None]:
        return installed_cli_runtime(cli, environment, log)


@pytest.fixture
def installed_process_world() -> InstalledProcessWorld:
    """Supply only process setup and lifetime; product tests own their assertions."""
    return RepositoryInstalledProcessWorld()
