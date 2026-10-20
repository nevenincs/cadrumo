"""Component identities move only when that component's own inputs change."""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from ...command_execution import run_command
from ..assemble import logical_inventory, package_fingerprint, stamp_package
from ..build_fingerprint import (
    COMPONENTS,
    FILE_API_QUERY,
    consumed_inputs,
    crate_closure,
    resolution_order,
    target_settings,
    uncovered_inputs,
)
from ..build_stamp import (
    BUILDING,
    SETTLED,
    UNSETTLED,
    BuildStamp,
    ComponentIdentity,
    begin_record,
    built_current,
    changed_inputs,
    identity_path,
    native_settled,
    read_record,
    record_built,
    resolve,
    settle_record,
)
from ..hashing import digest
from ..stdlib import bytecode

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

DAY = datetime(2026, 10, 19, 8, 30, tzinfo=UTC)

# A checkout reduced to the crates and sources the components declare, as pure input data.
CRATES = {
    "native/application": {},
    "native/platform": {},
    "native/launch_guard": {"cadrumo-application": "../application"},
    "native/installer": {"cadrumo-application": "../application"},
    "native/manager": {"cadrumo-application": "../application", "cadrumo-platform": "../platform"},
    "native/interpreter_host": {"cadrumo-launch-guard": "../launch_guard"},
    "native/desktop/src-tauri": {"cadrumo-platform": "../../platform", "cadrumo-application": "../../application"},
}
WINDOWS_ONLY = {
    "native/manager": {"cadrumo-installer": "../installer"},
    "native/desktop/src-tauri": {
        "cadrumo-manager": "../../manager",
        "cadrumo-installer": "../../installer",
        "cadrumo-interpreter-host": "../../interpreter_host",
    },
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _dependencies(table: dict[str, str]) -> str:
    return "".join(f'{name} = {{ path = "{path}" }}\n' for name, path in table.items())


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    for crate, dependencies in CRATES.items():
        manifest = f'[package]\nname = "{Path(crate).name}"\n\n[dependencies]\n{_dependencies(dependencies)}'
        if crate in WINDOWS_ONLY:
            manifest += f"\n[target.'cfg(windows)'.dependencies]\n{_dependencies(WINDOWS_ONLY[crate])}"
        manifest += '\n[dev-dependencies]\nfixture = { path = "../fixture-only" }\n'
        _write(root / crate / "Cargo.toml", manifest)
        _write(root / crate / "src/lib.rs", f"// {crate}\n")
        _write(root / crate / "tests/case.rs", "// test-only\n")
    _write(root / "native/interpreter/windows/host.c", "int main(void) { return 0; }\n")
    _write(root / "native/interpreter/bootstrap.py", "# staged Python, not compiled\n")
    _write(root / "native/manager/src/main.rs", "fn main() {}\n")
    return root


@pytest.fixture
def build(tmp_path: Path) -> Path:
    directory = tmp_path / "build"
    paths = {"generated": "generated", "desktop_frontend": "desktop/frontend"}
    _write(directory / "build-paths.json", json.dumps({"paths": paths}))
    _write(directory / "generated/identity.json", json.dumps({"version": "0.6.0"}))
    _write(directory / "generated/build-freeze.json", json.dumps({"number": "", "id": "", "date": ""}))
    _write(directory / "generated/contract.rs", "// contract\n")
    _write(directory / "desktop/frontend/index.html", "<!doctype html>\n")
    return directory


def _ids(build: Path, root: Path) -> dict[str, tuple[str, int]]:
    resolved = resolve(build, ["interpreter", "manager", "installer", "desktop"], now=DAY, root=root)
    return {name: (identity.stamp.build_id, identity.stamp.build_sequence) for name, identity in resolved.items()}


def test_the_crate_closure_follows_path_dependencies_of_every_target_but_not_tests(checkout: Path) -> None:
    assert crate_closure(("native/manager",), root=checkout) == [
        "native/application",
        "native/installer",
        "native/manager",
        "native/platform",
    ]


def test_embedded_components_resolve_first() -> None:
    assert resolution_order(["desktop"]) == ["desktop"]
    assert resolution_order(["manager"]) == ["manager"]
    assert resolution_order(["desktop-test-host"]) == ["desktop", "desktop-test-host"]
    assert set(COMPONENTS) == {"interpreter", "installer", "manager", "desktop", "desktop-test-host"}


def test_an_unchanged_checkout_keeps_every_identity_and_identity_file(build: Path, checkout: Path) -> None:
    first = _ids(build, checkout)
    files = {name: identity_path(build, name) for name in first}
    stamps = {name: (path.read_bytes(), path.stat().st_mtime_ns) for name, path in files.items()}
    # Touching a source changes its timestamp, never its content.
    host = checkout / "native/interpreter/windows/host.c"
    os.utime(host, ns=(host.stat().st_atime_ns, host.stat().st_mtime_ns + 10_000_000_000))
    assert _ids(build, checkout) == first
    assert {name: (path.read_bytes(), path.stat().st_mtime_ns) for name, path in files.items()} == stamps


def test_a_manager_executable_source_moves_only_the_manager(build: Path, checkout: Path) -> None:
    before = _ids(build, checkout)
    # The desktop links the manager library, never its executable's main.
    _write(checkout / "native/manager/src/main.rs", "fn main() { std::process::exit(0) }\n")
    after = _ids(build, checkout)
    assert after["manager"] != before["manager"]
    assert {name: after[name] for name in ("interpreter", "installer", "desktop")} == {
        name: before[name] for name in ("interpreter", "installer", "desktop")
    }


def test_a_manager_source_change_moves_the_manager_and_what_embeds_it_only(build: Path, checkout: Path) -> None:
    before = _ids(build, checkout)
    _write(checkout / "native/manager/src/lib.rs", "// edited\n")
    after = _ids(build, checkout)
    assert after["interpreter"] == before["interpreter"]
    assert after["installer"] == before["installer"]
    assert after["manager"] != before["manager"]
    assert after["desktop"] != before["desktop"]


def test_an_interpreter_host_change_leaves_the_manager_and_installer(build: Path, checkout: Path) -> None:
    before = _ids(build, checkout)
    _write(checkout / "native/interpreter/windows/host.c", "int main(void) { return 1; }\n")
    after = _ids(build, checkout)
    assert after["manager"] == before["manager"] and after["installer"] == before["installer"]
    assert after["interpreter"] != before["interpreter"]
    # The desktop links the interpreter host, so its own identity follows.
    assert after["desktop"] != before["desktop"]


def test_a_bridge_change_moves_the_interpreter_hosts_but_not_the_desktop(build: Path, checkout: Path) -> None:
    # The desktop links the C host source, not the CPython bridge, and compiles its own identity.
    _write(checkout / "native/interpreter/python.c", "/* bridge */\n")
    before = _ids(build, checkout)
    _write(checkout / "native/interpreter/python.c", "/* bridge, edited */\n")
    after = _ids(build, checkout)
    assert after["interpreter"] != before["interpreter"]
    assert {name: after[name] for name in ("desktop", "manager", "installer")} == {
        name: before[name] for name in ("desktop", "manager", "installer")
    }


def test_a_frontend_bundle_change_moves_only_the_desktop(build: Path, checkout: Path) -> None:
    before = _ids(build, checkout)
    _write(build / "desktop/frontend/index.html", "<!doctype html><title>edited</title>\n")
    after = _ids(build, checkout)
    assert {name: after[name] for name in ("interpreter", "installer", "manager")} == {
        name: before[name] for name in ("interpreter", "installer", "manager")
    }
    assert after["desktop"] != before["desktop"]


def test_tests_staged_python_and_bytecode_are_not_component_inputs(build: Path, checkout: Path) -> None:
    before = _ids(build, checkout)
    _write(checkout / "native/manager/tests/case.rs", "// another test\n")
    _write(checkout / "native/interpreter/bootstrap.py", "# edited staged Python\n")
    _write(checkout / "native/interpreter/__pycache__/bootstrap.cpython-313.pyc", "bytecode")
    assert _ids(build, checkout) == before


def test_reverting_a_change_restores_the_earlier_identity(build: Path, checkout: Path) -> None:
    before = _ids(build, checkout)
    source = checkout / "native/installer/src/lib.rs"
    original = source.read_text(encoding="utf-8")
    _write(source, "// edited\n")
    assert _ids(build, checkout)["installer"] != before["installer"]
    _write(source, original)
    assert _ids(build, checkout) == before


def test_the_package_fingerprint_derives_from_staged_files_and_component_fingerprints(
    build: Path, checkout: Path
) -> None:
    identities = resolve(build, ["desktop"], now=DAY, root=checkout)
    files = {"python.exe": "a" * 64, "data/registry.json": "b" * 64}
    base = package_fingerprint(files, identities, kind="application", build_type="debug")
    assert (
        package_fingerprint(dict(reversed(files.items())), identities, kind="application", build_type="debug") == base
    )
    assert (
        package_fingerprint(
            {**files, "data/registry.json": "c" * 64}, identities, kind="application", build_type="debug"
        )
        != base
    )
    assert package_fingerprint(files, identities, kind="application", build_type="release") != base
    _write(checkout / "native/manager/src/lib.rs", "// edited\n")
    changed = resolve(build, ["desktop"], now=DAY, root=checkout)
    assert package_fingerprint(files, changed, kind="application", build_type="debug") != base


NATIVE = ["interpreter", "installer", "manager", "desktop"]


def _all(build: Path, checkout: Path) -> dict[str, str]:
    resolved = resolve(build, NATIVE, now=DAY, root=checkout)
    return {name: identity.stamp.build_id for name, identity in resolved.items()}


def _toolchain(build: Path, *, rustc: str, node: str, uv: str = "c" * 64) -> None:
    files = {"rust/rustc": {"sha256": rustc}, "desktop/node": {"sha256": node}, "CADRUMO_UV": {"sha256": uv}}
    _write(build / "generated/build-toolchain.json", json.dumps({"builder_files": files, "tool_versions": {}}))


def _tool(name: str) -> str:
    found = shutil.which(name)
    assert found is not None, f"{name} is a native build prerequisite; install it and put it on PATH"
    return found


def test_a_rust_toolchain_change_moves_every_component_and_node_only_the_desktop(build: Path, checkout: Path) -> None:
    _toolchain(build, rustc="a" * 64, node="b" * 64)
    before = _all(build, checkout)
    _toolchain(build, rustc="a" * 64, node="d" * 64)
    after_node = _all(build, checkout)
    assert {name for name in NATIVE if after_node[name] != before[name]} == {"desktop"}
    _toolchain(build, rustc="e" * 64, node="d" * 64)
    after_rustc = _all(build, checkout)
    assert all(after_rustc[name] != after_node[name] for name in NATIVE)
    # The uv the Python producers use builds no native image.
    _toolchain(build, rustc="e" * 64, node="d" * 64, uv="f" * 64)
    assert _all(build, checkout) == after_rustc


def test_a_rust_flag_change_moves_every_component(build: Path, checkout: Path) -> None:
    before = _all(build, checkout)
    flags = {"target": "x86_64-pc-windows-msvc", "environment": {"RUSTFLAGS": "-C target-feature=+crt-static"}}
    _write(build / "generated/rust-environment.json", json.dumps(flags))
    after = _all(build, checkout)
    assert all(after[name] != before[name] for name in NATIVE)


def test_a_file_the_last_build_read_counts_even_when_undeclared(build: Path, checkout: Path) -> None:
    shared = checkout / "native/shared/strings.txt"
    _write(shared, "first\n")
    record = build / "cargo/native/x86_64-pc-windows-msvc/debug/cadrumo-manager.d"
    listed = " ".join(str(path).replace(" ", "\\ ") for path in (checkout / "native/manager/src/lib.rs", shared))
    _write(record, f"{build / 'cargo/native/out.exe'}: {listed}\n")
    assert uncovered_inputs("manager", build, root=checkout) == ["native/shared/strings.txt"]
    before = _all(build, checkout)
    _write(shared, "second\n")
    after = _all(build, checkout)
    assert after["manager"] != before["manager"]
    assert {name: after[name] for name in ("interpreter", "installer")} == {
        name: before[name] for name in ("interpreter", "installer")
    }


def test_compiler_read_logs_and_the_desktop_snapshot_map_back_to_the_checkout(build: Path, checkout: Path) -> None:
    header = checkout / "native/shared/extra.h"
    _write(header, "#define EXTRA 1\n")
    log = build / "native/cadrumo_python.dir/Debug/cadrumo_python.tlog/CL.read.1.tlog"
    log.parent.mkdir(parents=True)
    lines = [
        f"^{str(checkout / 'native/interpreter/windows/host.c').upper()}",
        str(header).upper(),
        "C:\\SDK\\WINDOWS.H",
    ]
    log.write_bytes(("\ufeff" + "\r\n".join(lines) + "\r\n").encode("utf-16-le"))
    assert set(consumed_inputs("interpreter", build, root=checkout)) == {
        "native/interpreter/windows/host.c",
        "native/shared/extra.h",
    }
    snapshot = build / "desktop/host/desktop/src-tauri/src/lib.rs"
    generated = build / "desktop/host/desktop/src-tauri/tauri.conf.json"
    _write(snapshot, "// snapshot\n")
    _write(generated, "{}\n")
    _write(build / "cargo/desktop/debug/cadrumo.d", f"{build / 'cadrumo.exe'}: {snapshot} {generated}\n")
    # The snapshot-only configuration is generated there, so only the snapshotted source counts.
    assert set(consumed_inputs("desktop", build, root=checkout)) == {"native/desktop/src-tauri/src/lib.rs"}


def test_a_real_cargo_build_reports_an_undeclared_source_it_compiled(
    tmp_path: Path, build: Path, checkout: Path
) -> None:
    cargo = _tool("cargo")
    host = run_command([_tool("rustc"), "-vV"], cwd=tmp_path).stdout
    triple = next(line.split(": ", 1)[1] for line in host.splitlines() if line.startswith("host: "))
    crate = checkout / "native/manager"
    _write(crate / "Cargo.toml", '[package]\nname = "cadrumo-manager"\nversion = "0.1.0"\nedition = "2024"\n')
    _write(
        crate / "src/main.rs",
        'const TEXT: &str = include_str!("../../shared/text.txt");\nfn main() { print!("{TEXT}") }\n',
    )
    _write(checkout / "native/shared/text.txt", "outside the crate\n")
    result = run_command(
        [cargo, "build", "--offline", "--target", triple, "--manifest-path", str(crate / "Cargo.toml")],
        cwd=tmp_path,
        environment=dict(os.environ, CARGO_TARGET_DIR=str(build / "cargo/native")),
    )
    assert result.returncode == 0, result.stderr
    assert uncovered_inputs("manager", build, root=checkout) == ["native/shared/text.txt"]


def test_the_cmake_file_api_names_each_targets_defines_and_flags(tmp_path: Path) -> None:
    cmake = _tool("cmake")
    source, binary = tmp_path / "project", tmp_path / "binary"
    _write(
        source / "CMakeLists.txt",
        "cmake_minimum_required(VERSION 3.25)\nproject(probe LANGUAGES C)\n"
        "add_executable(cadrumo_python host.c)\n"
        'target_compile_definitions(cadrumo_python PRIVATE "PROBE=${PROBE}")\n',
    )
    _write(source / "host.c", "int main(void) { return 0; }\n")
    _write(binary / FILE_API_QUERY, json.dumps({"requests": [{"kind": "codemodel", "version": 2}]}))

    def configure(probe: str) -> dict[str, Any]:
        result = run_command([cmake, "-S", str(source), "-B", str(binary), f"-DPROBE={probe}"], cwd=tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        return target_settings("interpreter", binary, root=source)

    first = configure("1")
    assert first and all(key.endswith("/cadrumo_python") for key in first)
    defines = {
        define
        for setting in first.values()
        if isinstance(setting, dict)
        for group in setting["compile"]
        for define in group["defines"]
    }
    assert "PROBE=1" in defines
    assert configure("1") == first
    assert configure("2") != first


def test_logical_package_content_ignores_relinked_bytes_but_not_their_component(tmp_path: Path) -> None:
    stamp = BuildStamp("2026101901", 1, "2026-10-19T08:30:00Z")
    identities = {"manager": ComponentIdentity("manager", "1" * 64, "0.6.0", stamp)}

    def stage(binary_digest: str) -> dict[str, str]:
        descriptor = [{"launch_image": "cadrumo-manager.exe", "image_digest": binary_digest, "descriptor_digest": "x"}]
        _write(tmp_path / "data/service-descriptors.json", json.dumps(descriptor))
        files = {"cadrumo-manager.exe": binary_digest, "data/service-descriptors.json": binary_digest[::-1]}
        return logical_inventory(
            tmp_path,
            files,
            [("manager", "cadrumo-manager.exe")],
            identities,
            descriptors="data/service-descriptors.json",
        )

    first = stage("a" * 64)
    assert stage("b" * 64) == first
    identities["manager"] = ComponentIdentity("manager", "2" * 64, "0.6.0", stamp)
    assert stage("a" * 64) != first


def test_logical_package_content_ignores_the_install_time_cache_key(tmp_path: Path) -> None:
    metadata = "lib/cadrumo-0.6.0.dist-info"

    def stage(installed: str, module: str) -> dict[str, str]:
        _write(tmp_path / f"{metadata}/uv_cache.json", json.dumps({"timestamp": installed}))
        _write(tmp_path / "lib/cadrumo/__init__.py", module)
        rows = [
            f"cadrumo/__init__.py,sha256={digest(tmp_path / 'lib/cadrumo/__init__.py')},{len(module)}",
            f"cadrumo-0.6.0.dist-info/uv_cache.json,sha256={digest(tmp_path / f'{metadata}/uv_cache.json')},20",
            "cadrumo-0.6.0.dist-info/RECORD,,",
        ]
        _write(tmp_path / f"{metadata}/RECORD", "\n".join(rows) + "\n")
        files = {path.relative_to(tmp_path).as_posix(): digest(path) for path in tmp_path.rglob("*") if path.is_file()}
        return logical_inventory(tmp_path, files, [], {}, descriptors=None)

    first = stage("08:45", "VALUE = 1\n")
    assert f"{metadata}/uv_cache.json" not in first
    # A reinstall of the same source stamps a new install time; the package content is unchanged.
    assert stage("08:59", "VALUE = 1\n") == first
    assert stage("09:10", "VALUE = 2\n") != first


def test_a_build_record_opens_on_change_settles_and_names_what_changed(build: Path, checkout: Path) -> None:
    _all(build, checkout)
    record = read_record(build, "manager")
    assert record is not None and record["state"] == BUILDING and record["inputs"] == "manager.inputs.json"
    assert native_settled(build, ["manager"], root=checkout) == {"manager": True}
    settle_record(
        build,
        "manager",
        settled=True,
        configuration="Debug",
        package="stage/Debug/app",
        artifacts={"cadrumo-manager.exe": "a" * 64},
    )
    settled = read_record(build, "manager")
    assert settled is not None and settled["state"] == SETTLED
    assert settled["staged"]["Debug"]["artifacts"] == {"cadrumo-manager.exe": "a" * 64}
    # An unchanged rebuild keeps the settled record and its staged artifacts.
    _all(build, checkout)
    assert read_record(build, "manager") == settled
    assert changed_inputs(build, "manager", root=checkout) == []
    _write(checkout / "native/manager/src/lib.rs", "// edited\n")
    assert changed_inputs(build, "manager", root=checkout) == ["native/manager/src/lib.rs"]
    assert native_settled(build, ["manager"], root=checkout) == {"manager": False}
    settle_record(build, "manager", settled=False)
    unsettled = read_record(build, "manager")
    assert unsettled is not None and unsettled["state"] == UNSETTLED
    _all(build, checkout)
    reopened = read_record(build, "manager")
    assert reopened is not None and reopened["state"] == BUILDING and reopened["staged"] == {}


def test_a_reused_image_needs_the_same_fingerprint_command_and_bytes(build: Path, checkout: Path) -> None:
    resolve(build, ["desktop"], configuration="Debug", now=DAY, root=checkout)
    image = build / "cargo/desktop/debug/cadrumo.exe"
    _write(image, "image\n")
    command = ["node", "tauri.mjs"]
    assert not built_current(build, "desktop", "Debug", image, command)
    record_built(build, "desktop", "Debug", image, command)
    assert built_current(build, "desktop", "Debug", image, command)
    assert not built_current(build, "desktop", "Debug", image, [*command, "--release"])
    assert not built_current(build, "desktop", "Release", image, command)
    _write(image, "relinked\n")
    assert not built_current(build, "desktop", "Debug", image, command)
    record_built(build, "desktop", "Debug", image, command)
    _write(checkout / "native/desktop/src-tauri/src/lib.rs", "// edited\n")
    resolve(build, ["desktop"], configuration="Debug", now=DAY, root=checkout)
    assert not built_current(build, "desktop", "Debug", image, command)


def test_the_package_identity_moves_only_with_what_the_stage_ships(build: Path, checkout: Path) -> None:
    paths = json.loads((build / "build-paths.json").read_text(encoding="utf-8"))["paths"]
    _write(build / "build-paths.json", json.dumps({"paths": {**paths, "stage": "stage"}}))
    resolve(build, ["interpreter"], configuration="Debug", now=DAY, root=checkout)
    stage = build / "stage/Debug/app"

    def staged(source: bytes) -> dict[str, str]:
        files = {
            "python.exe": b"host image",
            "lib/mod.py": source,
            "lib/__pycache__/mod.cpython-313.pyc": bytecode(source, "mod.py", prefix="lib"),
        }
        for member, content in files.items():
            (stage / member).parent.mkdir(parents=True, exist_ok=True)
            if not (stage / member).is_file() or (stage / member).read_bytes() != content:
                (stage / member).write_bytes(content)
        return {member: digest(stage / member) for member in files}

    def package(files: dict[str, str]) -> str:
        record, _, _ = stamp_package(
            build,
            stage,
            {"version": "0.6.0"},
            files,
            [("interpreter", "python.exe")],
            kind="application",
            build_type="debug",
            build_member="data/build.json",
            descriptors=None,
            packages="lib",
        )
        return str(record["build_id"])

    def payload(content: str) -> None:
        stamp = BuildStamp("2026101901", 1, "2026-10-19T08:30:00Z")
        begin_record(build, ComponentIdentity("app-payload", content * 64, "0.6.0", stamp), {"src/x.py": content})

    payload("a")
    first = package(staged(b"VALUE = 1\n"))
    # A checkout edit that changes no staged byte moves the payload's input fingerprint, not the package.
    payload("b")
    assert package(staged(b"VALUE = 1\n")) == first
    # Touching a staged source without changing it keeps its checked-hash bytecode, and the package.
    os.utime(stage / "lib/mod.py", ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
    assert package(staged(b"VALUE = 1\n")) == first
    # A changed staged byte moves the package; reverting it restores the identity even after
    # other packages took numbers in between.
    second = package(staged(b"VALUE = 2\n"))
    assert second != first
    assert package(staged(b"VALUE = 3\n")) not in {first, second}
    assert package(staged(b"VALUE = 1\n")) == first
