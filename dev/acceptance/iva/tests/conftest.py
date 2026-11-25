"""Shared installed-wheel CLI fixture for IVA acceptance journeys."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.packaging.acquire_common import venv_executable
from dev.packaging.google_oauth import GOOGLE_OAUTH_ENV
from dev.packaging.installed_wheel_binding import (
    assert_installed_console_entry_point,
    installed_wheel_payload_sha256,
)
from dev.packaging.release_cohort_support import client_venv_template
from dev.packaging.tests.test_google_oauth_provisioning import client_document


@pytest.fixture(scope="session")
def installed_wheel_aeat() -> Path:
    """Return the attested ``aeat`` launcher from the real installed product wheel."""
    # A session fixture runs before the function-scoped synthetic client exists,
    # so the cohort build subprocesses inherit a synthetic client directly.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(GOOGLE_OAUTH_ENV, client_document())
        template = client_venv_template()
    executable = venv_executable(template, "aeat").resolve(strict=True)
    assert_installed_console_entry_point(
        executable,
        distribution="cadrumo",
        entry_point="aeat",
        expected_value="cadrumo_runtime.host.frontend.cli.bootstrap:console_main",
    )
    payload_sha256 = installed_wheel_payload_sha256(executable)
    if len(payload_sha256) != 64:
        raise RuntimeError("installed Cadrumo wheel payload digest is invalid")
    return executable
