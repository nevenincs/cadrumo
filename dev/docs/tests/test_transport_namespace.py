"""Synthetic installed docs roots explicitly isolate transport across child launch."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.core.config import load_settings
from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location, storage_path
from cadrumo.tests.env_scope import isolated_aeat_env

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_fixture_socket_override_reaches_worker_but_not_strict_profile(tmp_path: Path) -> None:
    with isolated_aeat_env(), isolated_profile_storage_root(tmp_path=tmp_path) as root:
        location = storage_location(StorageCategory.RUNTIME_SOCKETS)
        assert location.settings_field is not None
        assert location.settings_field in load_settings().model_fields_set
        namespace = storage_path(StorageCategory.RUNTIME_SOCKETS)
        assert namespace.is_relative_to(root)
        assert namespace.is_dir()
        operator = child_environment(ChildEnvironmentProfile.OPERATOR, root)
        strict = child_environment(ChildEnvironmentProfile.STRICT, root)
        assert operator[location.settings_field.upper()] == str(namespace)
        assert location.settings_field.upper() not in strict
