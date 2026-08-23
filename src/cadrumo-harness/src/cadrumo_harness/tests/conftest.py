"""Shared fixtures for the harness package's source-only tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._plugin_cohort import TestPluginCohort, make_test_plugin_cohort


@pytest.fixture
def plugin_cohort(tmp_path: Path) -> TestPluginCohort:
    """Return a complete local wheel cohort outside each emitted tree."""
    return make_test_plugin_cohort(tmp_path / "sealed-input")

