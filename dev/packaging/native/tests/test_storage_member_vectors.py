"""Replay the authored member-override vectors against the CLI settings and the storage resolver.

The native platform replays the same vectors from the generated contract, so a
member spelling that one reader re-anchors and another refuses fails here or there.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.storage_environment import resolve_storage_path
from cadrumo.tests.env_scope import settings_without_env_file

from ..storage_vectors import StorageMemberVector, storage_member_vectors

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_HOST = "windows" if os.name == "nt" else "posix"
_VECTORS = tuple(vector for vector in storage_member_vectors() if vector.platform == _HOST)


def test_the_host_has_member_vectors() -> None:
    assert len(_VECTORS) >= 3
    assert {vector.platform for vector in storage_member_vectors()} == {"windows", "posix"}


def _expected(root: Path, vector: StorageMemberVector) -> Path:
    assert vector.expected_components is not None
    return root.joinpath(*vector.expected_components)


@pytest.mark.parametrize("vector", _VECTORS, ids=lambda vector: vector.name)
def test_storage_resolver_replays_the_member_vector(tmp_path: Path, vector: StorageMemberVector) -> None:
    root = tmp_path / "root"
    if vector.refusal is None:
        assert resolve_storage_path(vector.value, root=root, received={}) == _expected(root, vector)
    else:
        with pytest.raises(CoreValidationError) as error:
            resolve_storage_path(vector.value, root=root, received={})
        assert error.value.context is not None
        assert error.value.context["storage_root_refusal"] == vector.refusal
    assert not root.exists()


@pytest.mark.parametrize("vector", _VECTORS, ids=lambda vector: vector.name)
def test_cli_settings_replay_the_member_vector(tmp_path: Path, vector: StorageMemberVector) -> None:
    root = tmp_path / "root"
    field = vector.variable.lower()
    if vector.refusal is None:
        settings = settings_without_env_file(cadrumo_local_storage_root=root, **{field: vector.value})
        assert getattr(settings, field) == _expected(root, vector)
    else:
        with pytest.raises(CoreValidationError) as error:
            settings_without_env_file(cadrumo_local_storage_root=root, **{field: vector.value})
        assert error.value.context is not None
        assert error.value.context["storage_root_refusal"] == vector.refusal
