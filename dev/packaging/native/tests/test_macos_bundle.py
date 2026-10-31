"""Inside-out bundle sealing and seal verification of every bundle copy."""

from __future__ import annotations

import asyncio
import json
import os
import plistlib
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from .. import macos_bundle
from ..identity import identity
from ..layout import application_bundle, load_layout
from ..macos_bundle import (
    CodesignSeal,
    PackageTools,
    locate_bundle,
    nested_images,
    sealed_members,
    verify_packages,
    verify_runtime_role,
    verify_seal,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CODESIGN = Path("/usr/bin/codesign")
_SYNTHETIC_EXECUTABLES: set[Path] = set()
_THIN_ARM64 = b"\xcf\xfa\xed\xfe" + b"\0" * 28
_UNIVERSAL = b"\xca\xfe\xba\xbe" + b"\0" * 28

# A stand-in codesign that records each invocation and reports a hardened seal.
_RECORDING_CODESIGN = """import pathlib, sys
pathlib.Path(r"{log}").open("a", encoding="utf-8").write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1:2] == ["--display"]:
    sys.stderr.write("Identifier={application_id}\\n")
    sys.stderr.write("CodeDirectory v=20500 size=304 flags=0x10002(adhoc,runtime) hashes=3+3 location=embedded\\n")
    sys.stderr.write("Info.plist entries=13\\n")
    sys.stderr.write("Sealed Resources version=2 rules=13 files=2\\n")
"""


@pytest.fixture(autouse=True)
def _run_registered_python_executables(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run synthetic tool and runtime files through Python on Windows, with real processes."""
    _SYNTHETIC_EXECUTABLES.clear()
    real_run_command = run_command
    real_create_subprocess_exec = asyncio.create_subprocess_exec

    def command_with_python(argv: list[str] | tuple[str, ...]) -> list[str] | tuple[str, ...]:
        if argv and Path(argv[0]) in _SYNTHETIC_EXECUTABLES:
            return [sys.executable, *argv]
        return argv

    def adapted_run_command(argv, **kwargs):
        environment = kwargs.get("environment")
        adjusted = dict(kwargs)
        if argv and Path(argv[0]) in _SYNTHETIC_EXECUTABLES and environment is not None:
            environment = dict(environment)
            if "SYSTEMROOT" in os.environ:
                environment.setdefault("SystemRoot", os.environ["SYSTEMROOT"])
            adjusted["environment"] = environment
        return real_run_command(command_with_python(argv), **adjusted)

    async def adapted_create_subprocess_exec(program, *args, **kwargs):
        synthetic = Path(str(program)) in _SYNTHETIC_EXECUTABLES
        argv = command_with_python((str(program), *args))
        if sys.platform == "win32" and synthetic and kwargs.get("env") is not None:
            environment = dict(kwargs["env"])
            if "SYSTEMROOT" in os.environ:
                environment.setdefault("SystemRoot", os.environ["SYSTEMROOT"])
            kwargs["env"] = environment
        return await real_create_subprocess_exec(*argv, **kwargs)

    monkeypatch.setattr(macos_bundle, "run_command", adapted_run_command)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", adapted_create_subprocess_exec)
    yield
    _SYNTHETIC_EXECUTABLES.clear()


def _bundle(tmp_path: Path, bundle_id: str | None = None) -> tuple[Path, Path]:
    product = identity("macos-arm64")
    bundle = tmp_path / "stage" / f"{product.name}.app"
    contents = bundle / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources/app/bin").mkdir(parents=True)
    (contents / "Resources/app/data").mkdir(parents=True)
    main = contents / "MacOS/cadrumo"
    main.write_bytes(_THIN_ARM64)
    (contents / "Resources/app/data/build.json").write_text("{}", encoding="utf-8")
    info = {"CFBundleIdentifier": bundle_id or product.application_id, "CFBundleExecutable": "cadrumo"}
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))
    return bundle, main


def _recording_codesign(tmp_path: Path) -> tuple[Path, Path]:
    log = tmp_path / "codesign.log"
    tool = tmp_path / "tools/codesign"
    tool.parent.mkdir()
    tool.write_text(
        _RECORDING_CODESIGN.format(log=log, application_id=identity("macos-arm64").application_id), encoding="utf-8"
    )
    tool.chmod(0o755)
    _SYNTHETIC_EXECUTABLES.add(tool)
    return tool, log


def test_sealed_members_are_the_main_executable_and_the_resource_seal() -> None:
    wrapper = application_bundle(load_layout("macos-arm64"))
    assert wrapper is not None
    assert sealed_members("Cadrumo.app", wrapper, "cadrumo") == {
        "Cadrumo.app/Contents/MacOS/cadrumo",
        "Cadrumo.app/Contents/_CodeSignature/CodeResources",
    }


def test_nested_images_are_every_other_macho_and_no_data(tmp_path: Path) -> None:
    bundle, main = _bundle(tmp_path)
    payload = bundle / "Contents/Resources/app"
    (payload / "python").write_bytes(_THIN_ARM64)
    (payload / "bin/libpython.dylib").write_bytes(_UNIVERSAL)
    (payload / "data/notes.txt").write_text("not code", encoding="utf-8")
    (payload / "bin/linked").symlink_to(payload / "python")
    assert nested_images(bundle, main) == [payload / "bin/libpython.dylib", payload / "python"]


def test_seal_admits_nested_images_before_it_signs_the_bundle_last(tmp_path: Path) -> None:
    bundle, main = _bundle(tmp_path)
    nested = bundle / "Contents/Resources/app/bin/libpython.dylib"
    nested.write_bytes(_THIN_ARM64)
    tool, log = _recording_codesign(tmp_path)
    CodesignSeal(tool, "-").seal(bundle, main, identity("macos-arm64").application_id)
    calls = log.read_text(encoding="utf-8").splitlines()
    assert calls == [
        f"--verify --strict {nested}",
        f"--force --sign - --options runtime --timestamp=none {bundle}",
        f"--verify --deep --strict --verbose=2 {bundle}",
        f"--display --verbose=2 {bundle}",
    ]
    # Nested images keep the signatures their bytes were inventoried with.
    assert not any(call.startswith("--force") and str(nested) in call for call in calls)


def test_seal_refuses_a_main_executable_its_info_plist_does_not_declare(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path)
    other = bundle / "Contents/MacOS/other"
    other.write_bytes(_THIN_ARM64)
    tool, log = _recording_codesign(tmp_path)
    with pytest.raises(ValueError, match="main executable"):
        CodesignSeal(tool, "-").seal(bundle, other, identity("macos-arm64").application_id)
    assert not log.exists()


def test_verification_refuses_another_identity_or_a_seal_without_resources(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path)
    tool, _ = _recording_codesign(tmp_path)
    with pytest.raises(ValueError, match="distribution identifier"):
        verify_seal(tool, bundle, "md.neve.other")
    tool.write_text(
        tool.read_text(encoding="utf-8").replace(
            "Sealed Resources version=2 rules=13 files=2", "Sealed Resources=none"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="resource seal"):
        verify_seal(tool, bundle, identity("macos-arm64").application_id)


def test_seal_requires_an_explicit_identity_and_tool(tmp_path: Path) -> None:
    tool, _ = _recording_codesign(tmp_path)
    with pytest.raises(ValueError, match="explicit signing identity"):
        CodesignSeal(tool, "")
    with pytest.raises(ValueError, match="codesign tool"):
        CodesignSeal(Path("codesign"), "-")


def test_package_verification_locates_one_bundle_and_refuses_undeclared_formats(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path)
    assert locate_bundle(tmp_path / "stage", bundle.name) == bundle
    assert locate_bundle(tmp_path, bundle.name) == bundle
    (tmp_path / "second" / bundle.name).mkdir(parents=True)
    with pytest.raises(ValueError, match="exactly one"):
        locate_bundle(tmp_path, bundle.name)
    tool, _ = _recording_codesign(tmp_path)
    tools = PackageTools(tool, tool, tool, tool)
    with pytest.raises(ValueError, match="No bundle verification"):
        verify_packages(
            tools,
            [tmp_path / "package.pkg"],
            bundle.name,
            identity("macos-arm64").application_id,
            scratch_root=tmp_path,
        )


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires the native macOS codesign tool")
def test_ad_hoc_seal_is_inside_out_complete_and_breaks_on_later_change(tmp_path: Path) -> None:
    product = identity("macos-arm64")
    bundle, main = _bundle(tmp_path)
    # Signed system images stand in for the launcher and a nested image; nothing runs them.
    shutil.copyfile("/usr/bin/true", main)
    nested = bundle / "Contents/Resources/app/bin/tool"
    shutil.copyfile("/usr/bin/true", nested)
    unsigned = run_command([str(_CODESIGN), "--remove-signature", str(nested)], cwd=tmp_path)
    assert unsigned.returncode == 0, unsigned.stderr
    seal = CodesignSeal(_CODESIGN, "-")
    with pytest.raises(ValueError, match="codesign --verify failed"):
        seal.seal(bundle, main, product.application_id)
    assert not (bundle / "Contents/_CodeSignature").exists()
    signed = run_command([str(_CODESIGN), "--force", "--sign", "-", str(nested)], cwd=tmp_path)
    assert signed.returncode == 0, signed.stderr
    nested_bytes = nested.read_bytes()
    seal.seal(bundle, main, product.application_id)
    assert nested.read_bytes() == nested_bytes
    sealed = plistlib.loads((bundle / "Contents/_CodeSignature/CodeResources").read_bytes())
    assert {"Resources/app/data/build.json", "Resources/app/bin/tool"} <= sealed["files2"].keys()
    details = verify_seal(_CODESIGN, bundle, product.application_id)
    assert "Info.plist entries=" in details
    # A copy that preserves only bytes and modes keeps the seal valid.
    copy = tmp_path / "copy" / bundle.name
    shutil.copytree(bundle, copy, copy_function=shutil.copyfile)
    for source in bundle.rglob("*"):
        (copy / source.relative_to(bundle)).chmod(source.stat().st_mode & 0o777)
    verify_seal(_CODESIGN, copy, product.application_id)
    # Any write beneath the bundle after sealing is a broken seal, not a valid bundle.
    (copy / "Contents/Resources/app/data/build.json").write_text('{"changed": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="codesign --verify failed"):
        verify_seal(_CODESIGN, copy, product.application_id)
    (bundle / "Contents/_CodeSignature/CodeResources").unlink()
    with pytest.raises(ValueError, match="codesign --verify failed"):
        verify_seal(_CODESIGN, bundle, product.application_id)


def _runtime_main(main: Path, marker: Path, behavior: str) -> None:
    script = f'''import pathlib, sys, time
pathlib.Path(r"{marker}").write_text(" ".join(sys.argv[1:]) + "\\n", encoding="utf-8")
if {behavior!r} == "ready_and_stop":
    print('{{"kind":"runtime_ready","product_version":"1.2.3"}}', flush=True)
    sys.stdin.buffer.read()
elif {behavior!r} == "not_ready":
    sys.exit(3)
elif {behavior!r} == "ignore_close":
    print('{{"kind":"runtime_ready"}}', flush=True)
    time.sleep(30)
'''
    main.write_text(script, encoding="utf-8")
    main.chmod(0o755)
    _SYNTHETIC_EXECUTABLES.add(main)


def test_runtime_role_starts_between_two_seal_verifications(tmp_path: Path) -> None:
    bundle, main = _bundle(tmp_path)
    tool, log = _recording_codesign(tmp_path)
    marker = tmp_path / "ran"
    _runtime_main(main, marker, "ready_and_stop")
    assert verify_runtime_role(tool, bundle, identity("macos-arm64").application_id, scratch_root=tmp_path) == "1.2.3"
    assert marker.read_text(encoding="utf-8").strip() == "--role runtime --configured-root"
    verifications = [call for call in log.read_text(encoding="utf-8").splitlines() if "--deep" in call]
    assert len(verifications) == 2


def test_runtime_role_is_not_started_when_the_seal_is_refused(tmp_path: Path) -> None:
    bundle, main = _bundle(tmp_path)
    tool = tmp_path / "tools/codesign"
    tool.parent.mkdir()
    tool.write_text("raise SystemExit(1)\n", encoding="utf-8")
    tool.chmod(0o755)
    _SYNTHETIC_EXECUTABLES.add(tool)
    marker = tmp_path / "ran"
    _runtime_main(main, marker, "ready_and_stop")
    with pytest.raises(ValueError, match="codesign --verify failed"):
        verify_runtime_role(tool, bundle, identity("macos-arm64").application_id, scratch_root=tmp_path)
    assert not marker.exists()


def test_runtime_role_refuses_a_bundle_that_does_not_report_ready(tmp_path: Path) -> None:
    bundle, main = _bundle(tmp_path)
    tool, _ = _recording_codesign(tmp_path)
    _runtime_main(main, tmp_path / "ran", "not_ready")
    with pytest.raises(ValueError, match="did not report ready"):
        verify_runtime_role(tool, bundle, identity("macos-arm64").application_id, scratch_root=tmp_path)


def test_runtime_role_refuses_a_role_that_ignores_closed_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle, main = _bundle(tmp_path)
    tool, _ = _recording_codesign(tmp_path)
    monkeypatch.setattr(macos_bundle, "_RUNTIME_STOP_SECONDS", 1)
    _runtime_main(main, tmp_path / "ran", "ignore_close")
    with pytest.raises(ValueError, match="did not stop"):
        verify_runtime_role(tool, bundle, identity("macos-arm64").application_id, scratch_root=tmp_path)


@pytest.mark.parametrize("suffix", (".dmg", ".zip"))
@pytest.mark.parametrize("refuse_seal", (False, True))
def test_package_scratch_is_build_owned_and_cleaned_after_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str, *, refuse_seal: bool
) -> None:
    scratch = tmp_path / "testing"
    scratch.mkdir()
    package = tmp_path / f"package{suffix}"
    tools = PackageTools(*(tmp_path / name for name in ("codesign", "spctl", "hdiutil", "ditto")))
    calls: list[tuple[str, ...]] = []

    def run(tool: Path, *arguments: str) -> str:
        calls.append((tool.name, *arguments))
        if arguments[0] == "attach":
            assert "-readonly" in arguments
            destination = Path(arguments[arguments.index("-mountpoint") + 1])
        else:
            assert arguments[:2] == ("-x", "-k")
            destination = Path(arguments[-1])
        assert destination.is_relative_to(scratch)
        (destination / "Cadrumo.app").mkdir(parents=True)
        return ""

    def verify(tools: PackageTools, bundle: Path, application_id: str, label: str) -> None:
        assert bundle.is_dir() and bundle.is_relative_to(scratch)
        if refuse_seal:
            raise ValueError("refused seal")

    detached: list[Path] = []
    real_run_command = macos_bundle.run_command

    def detach(argv, **kwargs):
        if argv[1] == "detach":
            detached.append(Path(argv[-1]))
            return real_run_command([sys.executable, "-c", "pass"], **kwargs)
        raise AssertionError(argv)

    monkeypatch.setattr(macos_bundle, "_run", run)
    monkeypatch.setattr(macos_bundle, "_verify_copy", verify)
    monkeypatch.setattr(macos_bundle, "run_command", detach)
    if refuse_seal:
        with pytest.raises(ValueError, match="refused seal"):
            verify_packages(tools, [package], "Cadrumo.app", "application-id", scratch_root=scratch)
    else:
        verify_packages(tools, [package], "Cadrumo.app", "application-id", scratch_root=scratch)
    assert len(calls) == 1
    assert len(detached) == (1 if suffix == ".dmg" else 0)
    assert list(scratch.iterdir()) == []


def test_runtime_health_uses_the_explicit_build_testing_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle, main = _bundle(tmp_path)
    tool, _ = _recording_codesign(tmp_path)
    scratch = tmp_path / "testing"
    scratch.mkdir()
    roots: list[Path] = []

    async def ready(executable: Path, root: Path) -> str:
        assert executable == main
        assert root.is_dir() and root.parent == scratch
        assert not root.is_relative_to(bundle)
        roots.append(root)
        (root / "state").write_text("private", encoding="utf-8")
        return "1.2.3"

    monkeypatch.setattr(macos_bundle, "_serve_until_ready", ready)
    assert verify_runtime_role(tool, bundle, identity("macos-arm64").application_id, scratch_root=scratch) == "1.2.3"
    assert roots and not roots[0].exists()


@pytest.mark.parametrize("packaged", (False, True))
def test_cpack_verification_passes_its_own_binary_directory(tmp_path: Path, *, packaged: bool) -> None:
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("CMake is not installed")
    source = tmp_path / "source"
    module = source / "dev/packaging/native"
    module.mkdir(parents=True)
    for package in (module, module.parent, module.parent.parent):
        (package / "__init__.py").write_text("", encoding="utf-8")
    record = source / "arguments.json"
    (module / "macos_bundle.py").write_text(
        "import json, pathlib, sys\n"
        "pathlib.Path('arguments.json').write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )
    build = tmp_path / "build"
    build.mkdir()
    template = (REPO_ROOT / "native/cmake/distribution/MacosBundleVerify.cmake.in").read_text(encoding="utf-8")
    for name, value in {
        "CADRUMO_DEV_PYTHON": sys.executable,
        "CADRUMO_SOURCE_ROOT": source.as_posix(),
        "CMAKE_BINARY_DIR": build.as_posix(),
        "CADRUMO_PATH_GENERATED": (build / "generated").as_posix(),
        "CADRUMO_CODESIGN": (source / "codesign").as_posix(),
        "CADRUMO_SPCTL": (source / "spctl").as_posix(),
        "CADRUMO_HDIUTIL": (source / "hdiutil").as_posix(),
        "CADRUMO_DITTO": (source / "ditto").as_posix(),
    }.items():
        template = template.replace(f"@{name}@", value.replace("\\", "/"))
    staging = build / "stage"
    archive = build / "package.zip"
    prefix = (
        f'set(CPACK_PACKAGE_FILES "{archive.as_posix()}")\n'
        if packaged
        else f'set(CPACK_TEMPORARY_INSTALL_DIRECTORY "{staging.as_posix()}")\n'
    )
    script = build / "verify.cmake"
    script.write_text(prefix + template, encoding="utf-8")
    result = run_command([cmake, "-P", str(script)], cwd=source)
    assert result.returncode == 0, result.stderr
    arguments = json.loads(record.read_text(encoding="utf-8"))
    assert arguments[arguments.index("--build") + 1] == build.as_posix()
    if packaged:
        assert "verify-packages" in arguments and arguments[-1] == archive.as_posix()
    else:
        assert arguments[-3:] == ["verify-staging", "--root", staging.as_posix()]


def test_verification_cli_refuses_an_unenrolled_build_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    external = tmp_path / "arbitrary-build"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "macos_bundle",
            "--build",
            str(external),
            "--identity",
            str(tmp_path / "identity.json"),
            "--codesign",
            str(tmp_path / "codesign"),
            "verify-staging",
            "--root",
            str(tmp_path / "stage"),
        ],
    )
    with pytest.raises(SystemExit) as error:
        macos_bundle.main()
    assert error.value.code == 2
    assert not external.exists()
