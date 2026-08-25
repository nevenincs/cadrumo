"""Real cohort and archive tests for the secondary Cadrumo MCP Bundle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import textwrap
import time
import tomllib
import zipfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from dev.packaging.python_cohort import build_python_cohort, load_python_cohort
from dev.packaging.runtime_wheelhouse import load_runtime_wheelhouse

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_BUILD_PY = Path(__file__).resolve().parents[1] / "build.py"
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_build_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_cadrumo_mcpb_build", _BUILD_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BUILD = _load_build_module()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def real_cohort(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the one canonical sealed cohort API consumed by the bundle."""
    work = tmp_path_factory.mktemp("mcpb-real-cohort")
    clean_repo = work / "clean-repository"
    git = shutil.which("git")
    assert git is not None
    completed = subprocess.run(  # noqa: S603 - resolved Git with fixed local-clone argv.
        [git, "clone", "--local", "--no-hardlinks", str(_REPO_ROOT), str(clean_repo)],
        cwd=work,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    cohort_dir = work / "cohort"
    return build_python_cohort(clean_repo, cohort_dir).directory


def _copy_cohort(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    return destination


def _rewrite_digest(cohort_dir: Path, label: str) -> None:
    manifest_path = cohort_dir / "python-cohort.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = cohort_dir / document["artifacts"][label]
    document["sha256"][label] = _sha256(artifact)
    manifest_path.write_text(
        json.dumps(document, sort_keys=True),
        encoding="utf-8",
    )


def _load_bootstrap_namespace(bundle: Path) -> dict[str, object]:
    """Exec the staged bootstrap source with an injected ``__file__``.

    The bootstrap computes its bundle root from ``__file__``; injecting a path
    under ``bundle/src`` lets its pure provisioning-state logic be exercised
    without running ``uv`` or ``os.execv``. ``__name__`` is set to a non-main
    value so the module-level ``main()`` guard does not fire.
    """
    namespace: dict[str, object] = {
        "__file__": str(bundle / "src" / "server.py"),
        "__name__": "cadrumo_mcpb_bootstrap_under_test",
    }
    exec(compile(BUILD._BOOTSTRAP_SOURCE, "server.py", "exec"), namespace)  # noqa: S102 - bundle-owned source under test
    return namespace


def test_bootstrap_provisioning_state_is_keyed_on_the_cohort_marker(tmp_path: Path) -> None:
    """The bootstrap re-provisions only until the cohort marker matches the digest."""
    bundle = tmp_path / "extension"
    (bundle / "src").mkdir(parents=True)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CADRUMO_MCP_COHORT_SHA256", '{"cadrumo": "abc"}')
        namespace = _load_bootstrap_namespace(bundle)
        venv_python = cast("Callable[[], Path]", namespace["_venv_python"])()
        is_provisioned = cast("Callable[[Path], bool]", namespace["_is_provisioned"])
        # No venv interpreter yet: not provisioned, so the first launch provisions.
        assert is_provisioned(venv_python) is False
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("", encoding="utf-8")
        marker = cast("Path", namespace["_MARKER"])
        # Interpreter present but marker absent: still not provisioned.
        assert is_provisioned(venv_python) is False
        # Marker matching the cohort digest: provisioned, so a later launch
        # direct-execs and skips resolution.
        marker.write_text('{"cadrumo": "abc"}', encoding="utf-8")
        assert is_provisioned(venv_python) is True
        # A cohort-digest change (a version upgrade) invalidates the marker.
        patch.setenv("CADRUMO_MCP_COHORT_SHA256", '{"cadrumo": "def"}')
        assert is_provisioned(venv_python) is False


def test_bootstrap_guards_the_minimum_uv_for_constraint_dependencies(tmp_path: Path) -> None:
    """The first-launch bootstrap refuses a uv older than the pinned-closure floor."""
    floor = cast("str", BUILD._MIN_UV_VERSION)
    parts = floor.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
    triple = tuple(int(part) for part in parts)
    assert all(isinstance(number, int) for number in triple)

    bootstrap = cast("str", BUILD._BOOTSTRAP_SOURCE)
    # The generated source carries the literal floor and the version guard.
    assert f'_MIN_UV_VERSION = "{floor}"' in bootstrap
    assert '"--version"' in bootstrap
    assert "_require_min_uv" in bootstrap
    # The floor check runs before ``uv sync`` so an old uv cannot silently drop
    # the pinned closure.
    assert bootstrap.index("_require_min_uv(uv)") < bootstrap.index('"sync"')
    # The generated source parses and defines the guard as a callable.
    (tmp_path / "src").mkdir(parents=True)
    namespace = _load_bootstrap_namespace(tmp_path)
    assert callable(namespace["_require_min_uv"])
    assert callable(namespace["_uv_version_triple"])


def test_bootstrap_require_min_uv_refuses_a_below_floor_uv(tmp_path: Path) -> None:
    """A real uv launcher reporting a below-floor version drives the guard to SystemExit.

    Executing the guard against a launcher that prints ``uv 0.1.0`` proves the
    version comparison end to end (subprocess + parse + compare), so a ``<``/``>``
    inversion is detectable: an inverted comparison would stop refusing 0.1.0.
    """
    (tmp_path / "src").mkdir(parents=True)
    namespace = _load_bootstrap_namespace(tmp_path)
    require_min_uv = cast("Callable[[str], None]", namespace["_require_min_uv"])
    launcher = tmp_path / ("uv_stub" + (".cmd" if os.name == "nt" else ""))
    if os.name == "nt":
        launcher.write_text("@echo off\r\necho uv 0.1.0\r\n", encoding="utf-8")
    else:
        launcher.write_text('#!/bin/sh\necho "uv 0.1.0"\n', encoding="utf-8")
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IRUSR)

    with pytest.raises(SystemExit) as excinfo:
        require_min_uv(str(launcher))
    message = str(excinfo.value)
    assert cast("str", BUILD._MIN_UV_VERSION) in message
    assert "0.1.0" in message


def test_bootstrap_warm_path_serves_in_process_without_spawning(tmp_path: Path) -> None:
    """A provisioned bundle runs the real entry in-process, spawning nothing.

    Every launch after the first pays this path, and on Windows a spawn here
    costs two processes (the venv trampoline plus the base interpreter it
    starts). The premise is that ``uv run --no-project --directory <bundle>``
    still selects ``<bundle>/.venv``, so the bootstrap already IS the
    provisioned environment; the guard is ``sys.prefix``.

    Proven by making the subprocess module fail loudly: if the bootstrap tries
    to spawn on the warm path the test fails rather than silently regressing to
    the old process count. ``_serve.py`` is replaced by a marker-writing stub so
    no real cohort or server is needed.
    """
    bundle = tmp_path / "extension"
    (bundle / "src").mkdir(parents=True)
    venv = bundle / ".venv"
    venv.mkdir()
    marker = tmp_path / "served.txt"
    (bundle / "src" / "_serve.py").write_text(
        f"open({str(marker)!r}, 'w', encoding='utf-8').write('served in ' + str(__import__('os').getpid()))\n",
        encoding="utf-8",
    )

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CADRUMO_MCP_COHORT_SHA256", '{"cadrumo": "abc"}')
        namespace = _load_bootstrap_namespace(bundle)
        venv_python = cast("Callable[[], Path]", namespace["_venv_python"])()
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.write_text("", encoding="utf-8")
        cast("Path", namespace["_MARKER"]).write_text('{"cadrumo": "abc"}', encoding="utf-8")

        # Stand in for "this interpreter is the bundle venv" without building a
        # real venv, then make any spawn attempt a hard failure.
        namespace["_running_in_bundle_venv"] = lambda: True

        class _NoSpawn:
            def __getattr__(self, name: str) -> object:
                message = f"the warm path spawned a process via subprocess.{name}"
                raise AssertionError(message)

        namespace["subprocess"] = _NoSpawn()
        cast("Callable[[], None]", namespace["main"])()

    assert marker.exists(), "the warm path did not run the real entry at all"
    assert marker.read_text(encoding="utf-8").startswith("served in "), marker.read_text(encoding="utf-8")


def test_bootstrap_warm_path_guard_requires_the_bundle_venv(tmp_path: Path) -> None:
    """Serving in-process is gated on actually being the provisioned venv.

    The saving is only sound when this interpreter carries the installed cohort.
    An interpreter outside the bundle venv must fall through to the handoff, or
    a launch that resolved some other environment would try to serve without the
    cohort importable.
    """
    bundle = tmp_path / "extension"
    (bundle / "src").mkdir(parents=True)
    (bundle / ".venv").mkdir()
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CADRUMO_MCP_COHORT_SHA256", '{"cadrumo": "abc"}')
        namespace = _load_bootstrap_namespace(bundle)
        in_venv = cast("Callable[[], bool]", namespace["_running_in_bundle_venv"])
        # This test process is not the bundle venv, so the guard must decline.
        assert in_venv() is False


def test_bootstrap_supervised_server_cannot_outlive_a_killed_bootstrap(tmp_path: Path) -> None:
    """Killing the bootstrap reaps the server it supervises, leaving no orphan.

    On Windows the bootstrap cannot ``execv`` (CPython joins argv without
    quoting, and every real install lives under a spaced path), so it supervises
    the real server as a child. A plain child survives its parent's death and
    becomes a leaked MCP server holding its warm caches forever. The job object
    is what makes that impossible, and this proves it against real processes
    rather than trusting the flag.

    On POSIX the bootstrap ``execv``s, so there is no second process and no
    orphan is structurally possible; the assertion there is that no supervision
    is attempted at all.
    """
    (tmp_path / "src").mkdir(parents=True)
    namespace = _load_bootstrap_namespace(tmp_path)
    if os.name != "nt":
        # The POSIX branch replaces the process image; nothing to supervise.
        assert "os.execv" in cast("str", BUILD._BOOTSTRAP_SOURCE)
        return

    make_job = cast("Callable[[], object]", namespace["_kill_on_close_job"])
    assign = cast("Callable[[object, int], None]", namespace["_assign_to_job"])

    # A parent that builds the job, spawns a long-lived grandchild into it, and
    # then blocks - standing in for the bootstrap supervising the real server.
    parent_code = textwrap.dedent(
        f"""
        import subprocess, sys, time
        sys.path.insert(0, {str(tmp_path / "src")!r})
        ns = {{"__file__": {str(tmp_path / "src" / "server.py")!r}, "__name__": "probe"}}
        exec(compile(open({str(tmp_path / "src" / "bootstrap_src.py")!r}, encoding="utf-8").read(), "s", "exec"), ns)
        job = ns["_kill_on_close_job"]()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
        ns["_assign_to_job"](job, child.pid)
        print(child.pid, flush=True)
        time.sleep(300)
        """
    )
    (tmp_path / "src" / "bootstrap_src.py").write_text(cast("str", BUILD._BOOTSTRAP_SOURCE), encoding="utf-8")
    assert make_job() is not None, "the job object could not be created"
    assert callable(assign)

    parent = subprocess.Popen(  # noqa: S603 - fixed argv, test-owned source
        [sys.executable, "-c", parent_code],
        stdout=subprocess.PIPE,
        text=True,
    )
    grandchild_pid = 0
    try:
        assert parent.stdout is not None
        grandchild_pid = int(parent.stdout.readline())
        # The grandchild is genuinely running before the kill.
        assert _pid_running(grandchild_pid), "the supervised child never started"
        parent.kill()
        parent.wait(timeout=60)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if not _pid_running(grandchild_pid):
                break
            time.sleep(0.5)
        assert not _pid_running(grandchild_pid), (
            "the supervised server outlived its bootstrap; it would have leaked as an orphan"
        )
    finally:
        if parent.poll() is None:
            parent.kill()
        if grandchild_pid:
            subprocess.run(  # noqa: S603 - fixed argv
                ["taskkill", "/PID", str(grandchild_pid), "/F"],  # noqa: S607 - Windows system tool from PATH
                capture_output=True,
                check=False,
            )


def _pid_running(pid: int) -> bool:
    """Whether *pid* is a live process (Windows), by enumeration not OpenProcess."""
    completed = subprocess.run(  # noqa: S603 - fixed argv
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],  # noqa: S607 - Windows system tool from PATH
        capture_output=True,
        text=True,
        check=False,
    )
    return str(pid) in completed.stdout


def test_bootstrap_require_min_uv_accepts_an_at_or_above_floor_uv(tmp_path: Path) -> None:
    """A launcher reporting a version above the floor passes without SystemExit."""
    (tmp_path / "src").mkdir(parents=True)
    namespace = _load_bootstrap_namespace(tmp_path)
    require_min_uv = cast("Callable[[str], None]", namespace["_require_min_uv"])
    launcher = tmp_path / ("uv_ok" + (".cmd" if os.name == "nt" else ""))
    if os.name == "nt":
        launcher.write_text("@echo off\r\necho uv 99.0.0\r\n", encoding="utf-8")
    else:
        launcher.write_text('#!/bin/sh\necho "uv 99.0.0"\n', encoding="utf-8")
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IRUSR)

    require_min_uv(str(launcher))  # must not raise


def test_load_manifest_refuses_a_divergent_committed_author(tmp_path: Path) -> None:
    """The --check template gate refuses a committed author that is not the derived product author."""
    data = json.loads(Path(cast("Path", BUILD._MANIFEST)).read_text(encoding="utf-8"))
    author = cast("dict[str, object]", data["author"])
    author["name"] = "Someone Else"
    divergent = tmp_path / "manifest.json"
    divergent.write_text(json.dumps(data), encoding="utf-8")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(BUILD, "_MANIFEST", divergent)
        with pytest.raises(BUILD.ManifestError, match="must be the derived product author"):
            BUILD.load_manifest()


def test_constraints_header_states_the_minimum_uv_floor() -> None:
    """The staged constraints file names the uv floor the pins depend on."""
    from dev.packaging.uv_constraints import render_constraints_file

    floor = cast("str", BUILD._MIN_UV_VERSION)
    rendered = render_constraints_file(("example==1.0.0",), min_uv_version=floor)
    assert f"Requires uv >= {floor}" in rendered
    assert "constraint-dependencies" in rendered
    assert "example==1.0.0" in rendered
    # Backward-compatible default: no floor line when the caller omits it.
    assert "Requires uv" not in render_constraints_file(("example==1.0.0",))


def test_manifest_declares_only_the_bundle_local_python_runtime() -> None:
    """Unexecuted client/platform rows are not advertised as compatibility."""
    manifest = BUILD.load_manifest()
    assert manifest["manifest_version"] == "0.4"
    server = manifest["server"]
    assert server["type"] == "uv"
    assert server["entry_point"] == "src/server.py"
    assert server["mcp_config"] == {
        "command": "uv",
        "args": ["run", "--no-project", "--directory", "${__dirname}", "src/server.py"],
        "env": {
            "CADRUMO_LOCAL_STORAGE_ROOT": "${user_config.storage_root}",
            "CADRUMO_MCP_PERSONA": "${user_config.persona}",
            "CADRUMO_MCP_SURFACE": "${user_config.surface}",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": "",
        },
    }
    assert manifest["user_config"]["storage_root"] == {
        "type": "directory",
        "title": "Cadrumo state directory",
        "description": "Persistent, project-independent local state for the Cadrumo MCP service.",
        "required": True,
    }
    assert manifest["compatibility"] == {
        "runtimes": {"python": ">=3.13,<3.14"},
    }


def test_canonical_cohort_renders_bundle_local_sources(real_cohort: Path) -> None:
    """Every product dependency resolves from its canonical embedded wheel."""
    cohort = BUILD.load_cohort(real_cohort)
    project = tomllib.loads(BUILD.runtime_pyproject(cohort))
    assert project["project"]["dependencies"] == [
        f"cadrumo=={cohort.version}",
        f"cadrumo-harness=={cohort.harness_version}",
        f"cadrumo-data-manuals=={cohort.version}",
        f"cadrumo-data-official=={cohort.version}",
    ]
    sources = project["tool"]["uv"]["sources"]
    expected = {
        "cadrumo": cohort.root_wheel,
        "cadrumo-harness": cohort.harness_wheel,
        "cadrumo-data-manuals": cohort.manuals_wheel,
        "cadrumo-data-official": cohort.official_wheel,
    }
    for distribution, wheel in expected.items():
        assert sources[distribution] == {"path": f"artifacts/{wheel.name}"}
    # The transitive dependency closure is pinned from the tested uv.lock so the
    # first-launch ``uv sync`` cannot float to a fresh index resolution.
    constraints = project["tool"]["uv"]["constraint-dependencies"]
    assert constraints
    assert all("==" in requirement for requirement in constraints)


def test_build_contains_exact_wheels_and_canonical_digest_binding(
    tmp_path: Path,
    real_cohort: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Archive bytes and launch-time identity come from the canonical manifest."""
    cohort = BUILD.load_cohort(real_cohort)
    bundle = BUILD.build(cohort_dir=real_cohort, dist_dir=tmp_path)
    assert bundle.name == f"cadrumo-{cohort.version}.mcpb"
    expected_wheels = {
        cohort.root_wheel.name: cohort.root_wheel,
        cohort.harness_wheel.name: cohort.harness_wheel,
        cohort.manuals_wheel.name: cohort.manuals_wheel,
        cohort.official_wheel.name: cohort.official_wheel,
    }
    with zipfile.ZipFile(bundle) as archive:
        wheelhouse = load_runtime_wheelhouse(cohort.runtime_wheelhouse)
        expected_members = [
            f"artifacts/{cohort.root_wheel.name}",
            f"artifacts/{cohort.harness_wheel.name}",
            f"artifacts/{cohort.manuals_wheel.name}",
            f"artifacts/{cohort.official_wheel.name}",
            *(f"artifacts/wheelhouse/{filename}" for filename in sorted(wheelhouse.manifest["wheels"])),
            "artifacts/wheelhouse/runtime-wheelhouse.json",
            "constraints.txt",
            "manifest.json",
            "pyproject.toml",
            "src/_serve.py",
            "src/server.py",
        ]
        assert archive.namelist() == sorted(expected_members)
        for filename, wheel in expected_wheels.items():
            assert archive.read(f"artifacts/{filename}") == wheel.read_bytes()
        manifest = json.loads(archive.read("manifest.json"))
        constraints = archive.read("constraints.txt").decode()
        bootstrap = archive.read("src/server.py").decode()
        launcher = archive.read("src/_serve.py").decode()
    # The staged constraints file pins the transitive closure from the tested lock.
    constraint_lines = [line for line in constraints.splitlines() if line and not line.startswith("#")]
    assert constraint_lines
    assert all("==" in line for line in constraint_lines)
    expected_sha256 = {
        name: cohort.sha256[name]
        for name in (
            "cadrumo",
            "cadrumo-harness",
            "cadrumo-data-manuals",
            "cadrumo-data-official",
        )
    }
    env = manifest["server"]["mcp_config"]["env"]
    assert json.loads(env["CADRUMO_MCP_COHORT_SHA256"]) == expected_sha256
    assert env["CADRUMO_MCP_REQUIRED_VERSION"] == cohort.version
    assert env["CADRUMO_LOCAL_STORAGE_ROOT"] == "${user_config.storage_root}"
    assert "UV_PROJECT_ENVIRONMENT" not in env
    # The digest-pinned cohort verification lives in the real server entry, run
    # by the provisioned interpreter.
    assert "distribution(name)" in launcher
    assert 'read_text("direct_url.json")' in launcher
    # The bootstrap provisions the bundle-local venv once and direct-execs it
    # thereafter, so no session after the first re-resolves the project.
    assert "os.execv" in bootstrap
    assert "_serve.py" in bootstrap
    assert '"sync"' in bootstrap
    assert "distribution(name)" not in bootstrap
    assert "UNSIGNED; assembly only; client installation unproved" in capsys.readouterr().out


def test_unsigned_bundle_is_byte_reproducible(
    tmp_path: Path,
    real_cohort: Path,
) -> None:
    """Two assemblies of the exact real cohort produce identical MCPB bytes."""
    first = BUILD.build(cohort_dir=real_cohort, dist_dir=tmp_path / "first")
    second = BUILD.build(cohort_dir=real_cohort, dist_dir=tmp_path / "second")

    assert first.read_bytes() == second.read_bytes()


def test_missing_companion_is_rejected_by_the_canonical_validator(
    tmp_path: Path,
    real_cohort: Path,
) -> None:
    """MCPB cannot reinterpret an incomplete retained cohort."""
    candidate = _copy_cohort(real_cohort, tmp_path / "missing")
    cohort = load_python_cohort(candidate)
    cohort.official_wheel.unlink()
    with pytest.raises(BUILD.ManifestError, match="invalid Python cohort"):
        BUILD.load_cohort(candidate)


def test_mixed_companion_identity_is_rejected(
    tmp_path: Path,
    real_cohort: Path,
) -> None:
    """Digest-valid files still fail when a companion declares the wrong product."""
    candidate = _copy_cohort(real_cohort, tmp_path / "mixed")
    document = json.loads(
        (candidate / "python-cohort.json").read_text(encoding="utf-8"),
    )
    manuals = candidate / document["artifacts"]["cadrumo-data-manuals"]
    official = candidate / document["artifacts"]["cadrumo-data-official"]
    shutil.copy2(manuals, official)
    _rewrite_digest(candidate, "cadrumo-data-official")
    with pytest.raises(BUILD.ManifestError, match="identities or versions drifted"):
        BUILD.load_cohort(candidate)


def test_foreign_same_version_bytes_get_a_distinct_cohort_binding(
    tmp_path: Path,
    real_cohort: Path,
) -> None:
    """A second same-version cohort cannot satisfy the first cohort binding."""
    original = BUILD.load_cohort(real_cohort)
    candidate = _copy_cohort(real_cohort, tmp_path / "foreign")
    document = json.loads(
        (candidate / "python-cohort.json").read_text(encoding="utf-8"),
    )
    official = candidate / document["artifacts"]["cadrumo-data-official"]
    with zipfile.ZipFile(official, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("foreign-same-version-byte.txt", "different cohort\n")
    _rewrite_digest(candidate, "cadrumo-data-official")
    foreign = BUILD.load_cohort(candidate)
    assert foreign.version == original.version
    assert foreign.sha256["cadrumo-data-official"] != original.sha256["cadrumo-data-official"]
    original_env = BUILD.stamped_manifest(original)["server"]["mcp_config"]["env"]
    foreign_env = BUILD.stamped_manifest(foreign)["server"]["mcp_config"]["env"]
    assert original_env["CADRUMO_MCP_COHORT_SHA256"] != foreign_env["CADRUMO_MCP_COHORT_SHA256"]
    assert "UV_PROJECT_ENVIRONMENT" not in original_env
    assert "UV_PROJECT_ENVIRONMENT" not in foreign_env


def test_real_check_cli_reports_the_v04_template() -> None:
    """The public check validates the committed secondary-bundle template."""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [sys.executable, str(_BUILD_PY), "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "manifest.json valid: cadrumo" in completed.stdout
    assert completed.stderr == ""


def test_mcpb_identity_agrees_with_the_product(real_cohort: Path) -> None:
    """Bundle product names and version agree with installed product authority."""
    from cadrumo import __version__
    from cadrumo.core.product_identity import PRODUCT_IDENTITY

    cohort = BUILD.load_cohort(real_cohort)
    manifest = BUILD.stamped_manifest(cohort)
    assert manifest["version"] == cohort.version == __version__
    assert PRODUCT_IDENTITY.distribution == BUILD._DISTRIBUTIONS[0]
    assert PRODUCT_IDENTITY.companion_distributions == BUILD._DISTRIBUTIONS[1:]
    assert PRODUCT_IDENTITY.mcp_executable == BUILD._CONSOLE_SCRIPT
