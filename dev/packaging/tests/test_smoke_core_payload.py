"""Real wheel-member tests for the slim-core packaging smoke boundary."""

from __future__ import annotations

import shutil
import tomllib
import zipfile
from pathlib import Path

import pytest

from dev.packaging.smoke_core import (
    _CORPUS_SOURCE_PREFIX,
    _assert_complete_wheel_cohort,
    _build_companion_wheels,
    _build_wheel,
    _configured_corpus_binary_suffixes,
    _expected_wheel_data_paths,
    _is_corpus_source_binary,
    _tracked_source_data_paths,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REVIEW_FOUND_PATHS = {
    "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_349/files/"
    "02-349-orden-eha-769-2010-modificada-por-orden-eha-1721-2011-43-9-kb-docx.docx",
    "src/cadrumo/_data/corpus/aeat_official/instructions/modelo_289/files/289_XSD_2.0_WSDL_2.0.1.zip",
}


def test_core_wheel_contains_every_slim_member_and_no_split_owned_binary(tmp_path: Path) -> None:
    """Build the wheel and prove tracked-data parity against companion ownership."""
    uv = shutil.which("uv")
    assert uv is not None
    tracked = _tracked_source_data_paths(_REPO_ROOT)
    suffixes = _configured_corpus_binary_suffixes(_REPO_ROOT)
    split_owned = {path for path in tracked if "/tests/" not in path and _is_corpus_source_binary(path, suffixes)}
    assert split_owned >= _REVIEW_FOUND_PATHS

    wheel = _build_wheel(_REPO_ROOT, tmp_path, uv)
    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())

    independently_expected = {
        f"cadrumo/_data/{path.removeprefix('src/cadrumo/_data/')}"
        for path in tracked - split_owned
        if "/tests/" not in path
    }
    assert _expected_wheel_data_paths(_REPO_ROOT) == independently_expected
    assert independently_expected <= members
    assert not {f"cadrumo/_data/corpus/{path.removeprefix(_CORPUS_SOURCE_PREFIX)}" for path in split_owned} & members

    companions = _build_companion_wheels(_REPO_ROOT, tmp_path, uv)
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        expected_version = tomllib.load(handle)["project"]["version"]
    assert (
        _assert_complete_wheel_cohort(
            wheel,
            data_wheel_manuals=companions[0],
            data_wheel_official=companions[1],
        )
        == expected_version
    )
    with pytest.raises(SystemExit, match="labels do not match"):
        _assert_complete_wheel_cohort(
            wheel,
            data_wheel_manuals=companions[1],
            data_wheel_official=companions[0],
        )
