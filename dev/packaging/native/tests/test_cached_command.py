"""Real build actions reuse content and recover missing or damaged outputs."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..cached_command import run_cached

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_content_currency_and_output_recovery(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("one", encoding="utf-8")
    output = tmp_path / "out.txt"
    spec = tmp_path / "spec.json"
    marker = tmp_path / "receipt.json"
    spec.write_text(
        json.dumps({"name": "copy", "inputs": [str(source)], "outputs": [str(output)], "marker": str(marker)}),
        encoding="utf-8",
    )
    command = [
        sys.executable,
        "-c",
        "import shutil,sys; shutil.copyfile(sys.argv[1],sys.argv[2])",
        str(source),
        str(output),
    ]
    assert run_cached(tmp_path, spec, command)
    timestamp = output.stat().st_mtime_ns
    os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 2_000_000_000))
    assert not run_cached(tmp_path, spec, command)
    assert output.stat().st_mtime_ns == timestamp
    source.write_text("two", encoding="utf-8")
    assert run_cached(tmp_path, spec, command)
    assert output.read_text(encoding="utf-8") == "two"
    output.write_text("bad", encoding="utf-8")
    assert run_cached(tmp_path, spec, command)
    output.unlink()
    assert run_cached(tmp_path, spec, command)


def test_failed_action_does_not_publish_receipt(tmp_path: Path) -> None:
    spec = tmp_path / "spec.json"
    marker = tmp_path / "receipt.json"
    spec.write_text(
        json.dumps({"name": "failure", "inputs": [], "outputs": [str(tmp_path / "output")], "marker": str(marker)}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError):
        run_cached(tmp_path, spec, [sys.executable, "-c", "raise SystemExit(7)"])
    assert not marker.exists()


def test_changed_producer_inputs_refuse_receipt_and_record_failed_phase(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"original")
    output = tmp_path / "output"
    marker = tmp_path / "receipt.json"
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps({"name": "copy", "inputs": [str(source)], "outputs": [str(output)], "marker": str(marker)})
    )
    command = [
        sys.executable,
        "-c",
        "import pathlib,sys; a,b=map(pathlib.Path,sys.argv[1:]); "
        "b.write_bytes(a.read_bytes()); a.write_bytes(b'changed!')",
        str(source),
        str(output),
    ]
    with pytest.raises(RuntimeError, match="Inputs changed during copy"):
        run_cached(tmp_path, spec, command)
    assert not marker.exists()
    timing = json.loads(next((tmp_path / "timings").glob("copy-*.json")).read_text())
    assert any(phase["phase"] == "input-stability" and phase["outcome"] == "fail" for phase in timing["phases"])
    assert timing["phases"][-1]["phase"] == "total"
    assert timing["phases"][-1]["outcome"] == "fail"


def test_release_graph_materializes_bundle_and_archive_once(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    source = tmp_path / "source"
    source.mkdir()
    helper = source / "action.py"
    helper.write_text(
        "import pathlib,sys\n"
        "root=pathlib.Path(sys.argv[1]); name=sys.argv[2]\n"
        "counter=root/(name+'.calls')\n"
        "counter.write_text(counter.read_text()+'1' if counter.exists() else '1')\n"
        "if name=='bundle': (root/'payload').write_text('one generation')\n"
        "elif name=='zip': (root/'archive').write_bytes((root/'payload').read_bytes())\n"
        "else: assert (root/'archive').read_bytes()==(root/'payload').read_bytes()\n",
        encoding="utf-8",
    )
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(ReleaseGraph LANGUAGES NONE)\ninclude(CTest)\n"
        f'set(CADRUMO_DEV_PYTHON "{Path(sys.executable).as_posix()}")\n'
        f'add_custom_target(bundle COMMAND "${{CADRUMO_DEV_PYTHON}}" "{helper.as_posix()}" '
        '"${CMAKE_BINARY_DIR}" bundle)\n'
        f'add_custom_target(zip COMMAND "${{CADRUMO_DEV_PYTHON}}" "{helper.as_posix()}" '
        '"${CMAKE_BINARY_DIR}" zip DEPENDS bundle)\n'
        'add_test(NAME bundle-immutable COMMAND "${CMAKE_COMMAND}" -E compare_files '
        '"${CMAKE_BINARY_DIR}/payload" "${CMAKE_BINARY_DIR}/archive")\n'
        f'set(CADRUMO_HELPER "${{CADRUMO_DEV_PYTHON}}" "{helper.as_posix()}" "${{CMAKE_BINARY_DIR}}" acceptance)\n'
        "set(native_verification_targets bundle)\nset(CADRUMO_APPLICATION_ARTIFACT_PROBE_FILE unused)\n"
        f'include("{(REPO_ROOT / "native/cmake/ReleaseVerification.cmake").as_posix()}")\n',
        encoding="utf-8",
    )
    build = tmp_path / "build"
    for argv in (
        [cmake, "-S", str(source), "-B", str(build), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"],
        [cmake, "--build", str(build), "--target", "verify-release"],
    ):
        result = run_command(argv, cwd=REPO_ROOT)
        assert result.returncode == 0, result.stdout + result.stderr
    for name in ("bundle", "zip", "acceptance"):
        assert (build / f"{name}.calls").read_text() == "1"


def test_cmake_targets_reuse_siblings_and_cpack_uses_install(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    source = tmp_path / "source"
    source.mkdir()
    build = tmp_path / "build"
    for name in ("a", "b"):
        (source / name).write_text(name, encoding="utf-8")
    (source / "CMakeLists.txt").write_text(
        f'''cmake_minimum_required(VERSION 4.4)
project(Currency LANGUAGES NONE)
set(CADRUMO_DEV_PYTHON "{Path(sys.executable).as_posix()}")
include("{REPO_ROOT.as_posix()}/native/cmake/Cleanup.cmake")
include("{REPO_ROOT.as_posix()}/native/cmake/CachedCommand.cmake")
foreach(name a b)
  cadrumo_cached_command(wrapper ${{name}} INPUTS "${{CMAKE_SOURCE_DIR}}/${{name}}"
    OUTPUTS "${{CMAKE_BINARY_DIR}}/payload/${{name}}")
  add_custom_target(${{name}} ALL COMMAND ${{wrapper}} "${{CMAKE_COMMAND}}" -E copy
    "${{CMAKE_SOURCE_DIR}}/${{name}}" "${{CMAKE_BINARY_DIR}}/payload/${{name}}")
endforeach()
install(DIRECTORY "${{CMAKE_BINARY_DIR}}/payload/" DESTINATION . USE_SOURCE_PERMISSIONS)
set(CPACK_GENERATOR ZIP)
set(CPACK_PACKAGE_FILE_NAME fixture)
include(CPack)
cadrumo_finalize_clean_targets()
''',
        encoding="utf-8",
    )

    def run(*args: str) -> None:
        result = run_command([cmake, *args], cwd=REPO_ROOT)
        assert result.returncode == 0, result.stdout + result.stderr

    run("-S", str(source), "-B", str(build), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release")
    run("--build", str(build))
    sibling = build / "payload/b"
    before = sibling.stat().st_mtime_ns
    (source / "a").write_text("changed", encoding="utf-8")
    run("--build", str(build))
    assert (build / "payload/a").read_text(encoding="utf-8") == "changed"
    assert sibling.stat().st_mtime_ns == before
    run("--build", str(build), "--target", "clean-a")
    assert not (build / "payload/a").exists()
    assert sibling.stat().st_mtime_ns == before
    run("--build", str(build), "--target", "a")
    run("--build", str(build), "--target", "package")
    import zipfile

    with zipfile.ZipFile(build / "fixture.zip") as archive:
        assert sorted(Path(name).name for name in archive.namelist() if not name.endswith("/")) == ["a", "b"]
