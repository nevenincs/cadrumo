"""Unchanged payload stages skip on their build records; any real change still forces the work."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pytest

from .. import cmake_build
from ..action_cache import completed, fingerprint, resolve_paths
from ..build_stamp import BuildStamp, ComponentIdentity, begin_record, read_record, settle_record
from ..build_timing import measure_build
from ..cached_command import run_cached
from ..hashing import digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

STAMP = BuildStamp("2026102001", 1, "2026-10-20T08:00:00Z")


def _write(path: Path, content: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path


def _build(tmp_path: Path, paths: dict[str, str]) -> Path:
    build = tmp_path / "build"
    _write(build / "build-paths.json", json.dumps({"paths": {"generated": "generated", "timings": "timings", **paths}}))
    _write(build / "generated/identity.json", json.dumps({"target": "windows-x86-64", "version": "0.6.0"}))
    _write(build / "generated/build-freeze.json", json.dumps({"number": "", "id": "", "date": ""}))
    return build


def _phases(build: Path, action: str, seen: set[Path]) -> list[str]:
    """Return the phases of the one timing record ``action`` wrote since ``seen``."""
    fresh = sorted(set((build / "timings").glob(f"{action}-*.json")) - seen)
    assert len(fresh) == 1
    seen.update(fresh)
    return [phase["phase"] for phase in json.loads(fresh[0].read_text(encoding="utf-8"))["phases"]]


def test_the_action_fingerprint_keeps_its_value_when_read_through_the_digest_cache(tmp_path: Path) -> None:
    first = _write(tmp_path / "a.txt", "one")
    second = _write(tmp_path / "b.txt", "two")
    listing = _write(tmp_path / "inputs.txt", f"{second}\n{first}\n")
    expected = hashlib.sha256()
    for path in sorted((first, second)):
        expected.update(str(path.resolve()).encode("utf-8"))
        expected.update(hashlib.sha256(path.read_bytes()).digest())
    assert fingerprint(listing) == expected.hexdigest()


def test_batched_resolution_names_every_input_as_full_resolution_does(tmp_path: Path) -> None:
    real = _write(tmp_path / "real/module.py", "VALUE = 1\n").parent
    linked = tmp_path / "linked"
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(real), str(linked))
    else:
        linked.symlink_to(real, target_is_directory=True)
    paths = [real / "module.py", linked / "module.py", tmp_path / "missing.py", tmp_path / "real/../real/module.py"]
    assert resolve_paths(paths) == {path: path.resolve() for path in paths}


@pytest.mark.parametrize("change", ["none", "input", "staged-byte", "unsettled"])
def test_a_shared_producer_skips_only_on_its_receipt_and_settled_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    build = _build(tmp_path, {"agent": "inputs/agent", "stage": "stage"})
    _write(
        build / "generated/build-toolchain.json",
        json.dumps({"builder_files": {}, "desktop_tools": {"node": "node", "npm_cli": "npm-cli.js"}}),
    )
    source = _write(tmp_path / "source/agent.py", "VALUE = 1\n")
    listing = _write(tmp_path / "inputs-agent.txt", f"{source}\n")
    destination = build / "inputs/agent"
    calls: list[str] = []

    def producer(build: Path, arguments: argparse.Namespace, **kwargs: object) -> Path:
        # Stands in for the external wheel and Node builds; the reuse decision under test is real.
        calls.append(arguments.action)
        _write(destination / "wheels/agent.whl", source.read_bytes())
        return destination

    monkeypatch.setattr(cmake_build, "build_action", producer)
    arguments = argparse.Namespace(action="agent", inputs=listing)
    seen: set[Path] = set()

    def run() -> list[str]:
        with measure_build(build, "agent") as timings:
            cmake_build.execute_action(build.resolve(), arguments, timings)
        return _phases(build, "agent", seen)

    run()
    assert calls == ["agent"]
    # Assembly staged the agent's RECORD and settled the record with its digest.
    staged = _write(build / "stage/Release/app/lib/cadrumo_agent-1.dist-info/RECORD", "cadrumo_agent/__init__.py\n")
    settle_record(
        build,
        "app-agent",
        settled=True,
        configuration="Release",
        package="stage/Release/app",
        artifacts={"lib/cadrumo_agent-1.dist-info/RECORD": digest(staged)},
    )
    if change == "input":
        source.write_text("VALUE = 2\n", encoding="utf-8")
    elif change == "staged-byte":
        staged.write_text("cadrumo_agent/changed.py\n", encoding="utf-8")
    elif change == "unsettled":
        settle_record(build, "app-agent", settled=False)
    phases = run()
    if change == "none":
        # Decided from the receipt and the record alone: the outputs are not read back.
        assert calls == ["agent"]
        assert "record-currency" in phases
        assert "existing-output-inventory" not in phases
    elif change == "input":
        assert calls == ["agent", "agent"]
        assert "producer" in phases
    else:
        # The record no longer vouches for the outputs, so every output is verified again.
        assert "existing-output-inventory" in phases
        assert calls == ["agent"]
        record = read_record(build, "app-agent")
        assert record is not None
        assert record["state"] == "settled"


_PRODUCER = (
    "import pathlib, sys\n"
    "source, app, ready, calls = map(pathlib.Path, sys.argv[1:])\n"
    "calls.write_text(calls.read_text() + '1' if calls.exists() else '1')\n"
    "for member in ('data/package-manifest.json', 'lib/deep/package/module.py'):\n"
    "    target = app / member\n"
    "    target.parent.mkdir(parents=True, exist_ok=True)\n"
    "    target.write_bytes(source.read_bytes())\n"
    "ready.write_text('complete\\n')\n"
)


@pytest.mark.parametrize("change", ["none", "input", "producer-output", "staged-byte", "unsettled"])
def test_assembly_skips_only_while_its_inputs_records_and_staged_artifacts_hold(
    tmp_path: Path, capfd: pytest.CaptureFixture[str], change: str
) -> None:
    # The producer inherits the descriptor-backed output streams fd capture provides.
    build = _build(tmp_path, {})
    source = _write(tmp_path / "source.py", "VALUE = 1\n")
    product = build / "product"
    _write(product / "dependencies/dist/module.py", "PRODUCT = 1\n")
    completed(product, "product-inputs-1")
    app = build / "stage/Release/app"
    ready = build / "stage/Release/ready"
    calls = tmp_path / "calls"
    spec = _write(
        build / "action-app-payload-Release.json",
        json.dumps(
            {
                "name": "app-payload",
                "inputs": [str(source), str(product / "dependencies")],
                "outputs": [str(app), str(ready)],
                "marker": str(build / "generated/action-app-payload-Release.json"),
            }
        ),
    )
    command = [sys.executable, "-c", _PRODUCER, str(source), str(app), str(ready), str(calls)]
    seen: set[Path] = set()

    def run() -> bool:
        ran = run_cached(build, spec, command)
        phases.extend(_phases(build, "app-payload", seen))
        return ran

    phases: list[str] = []
    assert run()
    # The assembly staged a native image record, settled with the digest of a deep artifact.
    begin_record(build, ComponentIdentity("manager", "a" * 64, "0.6.0", STAMP), {"native/manager/src/main.rs": "a"})
    settle_record(
        build,
        "manager",
        settled=True,
        configuration="Release",
        package="stage/Release/app",
        artifacts={"lib/deep/package/module.py": digest(app / "lib/deep/package/module.py")},
    )
    if change == "input":
        source.write_text("VALUE = 2\n", encoding="utf-8")
    elif change == "producer-output":
        # The producer rebuilt its destination: new bytes and a new completion receipt.
        (product / "ready").unlink()
        _write(product / "dependencies/dist/module.py", "PRODUCT = 2\n")
        completed(product, "product-inputs-2")
    elif change == "staged-byte":
        (app / "lib/deep/package/module.py").write_text("VALUE = 9\n", encoding="utf-8")
    elif change == "unsettled":
        settle_record(build, "manager", settled=False)
    phases.clear()
    ran = run()
    if change == "none":
        assert not ran
        assert "record-currency" in phases
        assert "input-inventory" not in phases
        assert calls.read_text() == "1"
    elif change == "unsettled":
        # Nothing vouches for the package any more: every input and output is compared again.
        assert not ran
        assert "input-inventory" in phases
    else:
        assert ran
        assert calls.read_text() == "11"
