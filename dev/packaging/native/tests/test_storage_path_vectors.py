"""Replay authored filesystem fixtures against the Python host boundary."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.storage_environment import STORAGE_ROOT, StorageMode, StorageModeEvidence, storage_root_for
from cadrumo.tests.audited_process import run_audited_process

from ..storage_vectors import StoragePathVector, storage_path_vectors

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("vector", storage_path_vectors(), ids=lambda vector: vector.name)
def test_host_resolver_replays_original_and_normalized_link_fixtures(tmp_path: Path, vector: StoragePathVector) -> None:
    for directory in vector.directories:
        (tmp_path / directory).mkdir()
    for file in vector.files:
        (tmp_path / file).write_text("fixture")
    for name, target in vector.links:
        if os.name == "nt":
            command = [os.environ["COMSPEC"], "/c", "mklink", "/J", str(tmp_path / name), str(tmp_path / target)]
            result = run_audited_process(command, capture_output=True, timeout=20)
            assert result.returncode == 0, (result.stdout, result.stderr)
        else:
            (tmp_path / name).symlink_to(tmp_path / target)
    environment = {STORAGE_ROOT.variable: str(tmp_path.joinpath(*vector.components))}
    if vector.refusal is None:
        assert vector.expected_components is not None
        assert storage_root_for(environment, StorageModeEvidence(StorageMode.INSTALLED, None)) == tmp_path.joinpath(
            *vector.expected_components
        )
    else:
        with pytest.raises(CoreValidationError) as error:
            storage_root_for(environment, StorageModeEvidence(StorageMode.INSTALLED, None))
        assert error.value.context is not None
        assert error.value.context["storage_root_refusal"] == vector.refusal.value
    assert not (tmp_path / "selected").exists() and not (tmp_path / "missing").exists()
