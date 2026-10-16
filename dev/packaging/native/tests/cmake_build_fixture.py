"""Create an enrolled synthetic source tree for CMake CLI integration tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT


def enrolled_cmake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / "build").mkdir(parents=True)
    (root / "CMakePresets.json").write_text('{"configurePresets":[{"name":"native-fixture"}]}', encoding="utf-8")
    desktop = root / "native/desktop"
    desktop.mkdir(parents=True)
    (desktop / "CMakePresets.json").write_text('{"configurePresets":[{"name":"desktop-fixture"}]}', encoding="utf-8")
    distribution = root / "native/cmake/distribution"
    distribution.mkdir(parents=True)
    (distribution / "CMakePresets.json").write_text(
        '{"configurePresets":[{"name":"distribution-fixture"}]}', encoding="utf-8"
    )
    (root / "sitecustomize.py").write_text(
        "from pathlib import Path\n"
        "from dev.packaging.native import build_directory\n"
        "build_directory.REPO_ROOT = Path(__file__).resolve().parent\n",
        encoding="utf-8",
    )
    path_entries = [str(REPO_ROOT), str(root)]
    inherited = os.environ.get("PYTHONPATH")
    if inherited is not None and inherited:
        path_entries.append(inherited)
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(path_entries))
    return root, root / "build/native-fixture"


def build_manifest_cmake() -> str:
    return (
        'set(_fixture_source "${CMAKE_SOURCE_DIR}")\n'
        'string(REPLACE "\\\\" "/" _fixture_source "${_fixture_source}")\n'
        'set(_fixture_manifest "{\\"paths\\":{\\"testing\\":\\"testing\\",'
        '\\"stage\\":\\"stage\\",\\"generated\\":\\"generated\\"}}")\n'
        'string(JSON _fixture_manifest SET "${_fixture_manifest}" source "\\"${_fixture_source}\\"")\n'
        'file(WRITE "${CMAKE_BINARY_DIR}/build-paths.json" "${_fixture_manifest}\\n")\n'
    )
