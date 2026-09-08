"""Child-pytest probe for the real cache and temporary-directory bindings."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from cadrumo.tests.collection_storage_root import collection_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_write_resolved_pytest_paths(tmp_path_factory: pytest.TempPathFactory, pytestconfig: pytest.Config) -> None:
    """Write paths for the parent integration test without asserting its setup."""
    destination = Path(os.environ["CADRUMO_PYTEST_PATH_PROBE"])
    destination.write_text(
        json.dumps(
            {
                "basetemp": str(tmp_path_factory.getbasetemp()),
                "cache": str(pytestconfig.cache._cachedir),
                "run_root": os.environ["CADRUMO_TEST_RUN_ROOT"],
                "stdlib_temp": tempfile.gettempdir(),
                "storage_root": str(collection_storage_root()),
            }
        ),
        encoding="utf-8",
    )
