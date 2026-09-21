"""Shared installed-wheel CLI fixture for IVA acceptance journeys."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.packaging._acquire_common import venv_executable
from dev.packaging._installed_wheel_binding import (
    assert_installed_console_entry_point,
    installed_wheel_payload_sha256,
)
from dev.packaging.release_cohort_support import client_venv_template


@pytest.fixture(scope="session")
def installed_wheel_aeat() -> Path:
    """Return the attested ``aeat`` launcher from the real installed product wheel."""
    executable = venv_executable(client_venv_template(), "aeat").resolve(strict=True)
    assert_installed_console_entry_point(
        executable,
        distribution="cadrumo",
        entry_point="aeat",
        expected_value="cadrumo.entrypoints.cli.bootstrap:main",
    )
    payload_sha256 = installed_wheel_payload_sha256(executable)
    if len(payload_sha256) != 64:
        raise RuntimeError("installed Cadrumo wheel payload digest is invalid")
    return executable
