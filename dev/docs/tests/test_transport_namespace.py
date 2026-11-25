"""A launched child derives the same connection namespace from the storage root alone.

The connection namespace has no variable of its own: it sits at its declared
subpath beneath the storage root, and the root is the one setting a launcher
hands a child. This holds for every child profile, so a docs build or worker
started under a synthetic root addresses the namespace its parent resolved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.core.config import Settings
from cadrumo.core.storage_environment import STORAGE_ROOT, ChildEnvironmentProfile, child_environment
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location, storage_path
from cadrumo.tests.env_scope import isolated_aeat_env

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("profile", list(ChildEnvironmentProfile))
def test_a_child_derives_the_parents_connection_namespace_from_the_root_alone(
    tmp_path: Path, profile: ChildEnvironmentProfile
) -> None:
    with isolated_aeat_env(), isolated_profile_storage_root(tmp_path=tmp_path) as root:
        location = storage_location(StorageCategory.CONNECTION_SOCKETS)
        namespace = storage_path(StorageCategory.CONNECTION_SOCKETS)
        assert namespace == root / location.relative_path()
        assert location.runtime_owned, "only the runtime creates the namespace, so a launched child never has to"
        assert not namespace.exists()

        received = {STORAGE_ROOT.variable: str(tmp_path / "ambient-root")}
        environment = child_environment(profile, root, received=received)
        assert environment[STORAGE_ROOT.variable] == str(root.resolve()), "the launcher's root outranks a received one"

    with isolated_aeat_env(**{STORAGE_ROOT.variable: environment[STORAGE_ROOT.variable]}):
        assert storage_path(StorageCategory.CONNECTION_SOCKETS, settings=Settings()) == namespace.resolve()
