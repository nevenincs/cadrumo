"""Generated desktop commands preserve the admitted Node path and inherited PATH."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_generated_desktop_command_preserves_multi_entry_path(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    assert cmake is not None and node is not None and npm is not None
    inherited = os.pathsep.join((str(tmp_path / "path with spaces"), str(tmp_path / "second path"), os.environ["PATH"]))
    probe = tmp_path / "probe.cjs"
    baseline_path = tmp_path / "baseline.json"
    probe.write_text(
        'const fs=require("fs"); const child=require("child_process").spawnSync("node",["-e",'
        '"process.stdout.write(process.execPath)"],{encoding:"utf8"}); '
        "if(child.error||child.status)throw child.error||new Error(child.stderr); "
        "fs.writeFileSync(process.argv[2],JSON.stringify({path:process.env.PATH,child:child.stdout}));\n",
        encoding="utf-8",
    )
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(DesktopPathProbe LANGUAGES NONE)\n"
        f'set(CADRUMO_NODE "{Path(node).as_posix()}")\nset(CADRUMO_NPM "{Path(npm).as_posix()}")\n'
        f'include("{(REPO_ROOT / "native/cmake/DesktopTools.cmake").as_posix()}")\n'
        f'add_custom_target(probe COMMAND "${{CADRUMO_NODE}}" "{probe.as_posix()}" "{baseline_path.as_posix()}"\n'
        ' COMMAND "${CMAKE_COMMAND}" -E env ${desktop_node_path_arguments}\n'
        f' "${{CADRUMO_NODE}}" "{probe.as_posix()}" "{(tmp_path / "result.json").as_posix()}" VERBATIM)\n',
        encoding="utf-8",
    )
    environment = dict(os.environ, PATH=inherited)
    generator = "Visual Studio 17 2022" if os.name == "nt" else "Ninja"
    configured = run_command(
        [cmake, "-G", generator, "-S", str(tmp_path), "-B", str(tmp_path / "build")],
        cwd=tmp_path,
        environment=environment,
    )
    assert configured.returncode == 0, configured.stderr
    result = run_command(
        [cmake, "--build", str(tmp_path / "build"), "--config", "Release", "--target", "probe"],
        cwd=tmp_path,
        environment=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert str(tmp_path / "path with spaces") in baseline["path"].split(os.pathsep)
    assert str(tmp_path / "second path") in baseline["path"].split(os.pathsep)
    assert observed["path"] == os.pathsep.join((str(Path(node).parent), baseline["path"]))
    assert Path(observed["child"]).resolve() == Path(node).resolve()
