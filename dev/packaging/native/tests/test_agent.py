"""Exercise the private wheel's source identity, checksum admission and dependency resolution."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from ...runtime_wheel_selection import marker_environment
from ...runtime_wheelhouse_contract import target_platform
from ..agent import (
    AGENT_DEPENDENCIES,
    AGENT_DEPENDENCY_RECORD,
    DependencyGateError,
    ResolvedDistribution,
    agent_wheel,
    build_agent,
    gate_environment,
    locked_distributions,
    require_python_step_lock,
    require_single_lock_provenance,
    resolve_shared_dependencies,
    resolved_requirements,
)
from ..target import uv_platform

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WINDOWS = marker_environment(target_platform("windows-x86-64"), "3.13.11")


def wheel_tree(root: Path) -> Path:
    """Create an independently hashed build receipt for an inert wheel payload."""
    wheels = root / "wheels"
    wheels.mkdir()
    wheel = wheels / "cadrumo_agent-0.1.0-py3-none-any.whl"
    payload = b"agent wheel admission fixture"
    wheel.write_bytes(payload)
    record = dict(
        source="configured-folder", version="0.1.0", wheel=wheel.name, wheel_sha256=hashlib.sha256(payload).hexdigest()
    )
    (root / "agent-wheel.json").write_text(json.dumps(record), encoding="utf-8")
    return wheel


def test_built_agent_wheel_is_admitted(tmp_path: Path) -> None:
    """A matching source identity and wheel checksum resolves the built artifact."""
    wheel = wheel_tree(tmp_path)
    assert agent_wheel(tmp_path) == wheel


def test_changed_wheel_is_refused(tmp_path: Path) -> None:
    """Changing bytes after construction cannot reuse the wheel receipt."""
    wheel = wheel_tree(tmp_path)
    wheel.write_bytes(b"changed after build")
    with pytest.raises(ValueError, match="checksum mismatch"):
        agent_wheel(tmp_path)


def _wheel(directory: Path, name: str, version: str, requires: Sequence[str] = ()) -> None:
    """Write one minimal pure-Python wheel whose metadata declares ``requires``."""
    directory.mkdir(parents=True, exist_ok=True)
    stem = name.replace("-", "_")
    info = f"{stem}-{version}.dist-info"
    metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    metadata += "".join(f"Requires-Dist: {requirement}\n" for requirement in requires)
    with zipfile.ZipFile(directory / f"{stem}-{version}-py3-none-any.whl", "w") as archive:
        archive.writestr(f"{stem}/__init__.py", "")
        archive.writestr(f"{info}/METADATA", metadata)
        archive.writestr(
            f"{info}/WHEEL", "Wheel-Version: 1.0\nGenerator: fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        )
        archive.writestr(f"{info}/RECORD", "")


def _locked(index: Path, versions: Mapping[str, str]) -> dict[str, ResolvedDistribution]:
    """Record each version with the hash of the wheel the fixture index serves, as a lock does."""
    locked = {}
    for name, version in versions.items():
        wheel = index / f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
        recorded = hashlib.sha256(wheel.read_bytes()).hexdigest() if wheel.is_file() else "0" * 64
        locked[name] = ResolvedDistribution(version, (recorded,))
    return locked


def _resolve(
    tmp_path: Path,
    *,
    cadrumo_declared: Sequence[str],
    agent_declared: Sequence[str],
    cadrumo_locked: Mapping[str, str],
    agent_locked: Mapping[str, str],
    recorded: Mapping[str, ResolvedDistribution] | None = None,
) -> dict[str, ResolvedDistribution]:
    uv = shutil.which("uv")
    assert uv is not None
    index = tmp_path / "index"
    index.mkdir(exist_ok=True)
    return resolve_shared_dependencies(
        cadrumo_declared=[Requirement(value) for value in cadrumo_declared],
        agent_declared=[Requirement(value) for value in agent_declared],
        cadrumo_locked={**_locked(index, cadrumo_locked), **(recorded or {})},
        agent_locked=_locked(index, agent_locked),
        python="3.13.11",
        platform=uv_platform("windows-x86-64"),
        uv=uv,
        work=tmp_path / "work",
        repositories={"Cadrumo": tmp_path / "cadrumo", "cadrumo-agent": tmp_path / "cadrumo-agent"},
        index_arguments=("--no-index", "--find-links", str(tmp_path / "index")),
    )


def test_newest_admissible_shared_version_is_selected(tmp_path: Path) -> None:
    """When both locked versions satisfy both projects, the newer one ships."""
    for version in ("1.0", "2.0"):
        _wheel(tmp_path / "index", "shared", version)
    _wheel(tmp_path / "index", "agent-only", "1.0", ["shared>=1"])
    resolved = _resolve(
        tmp_path,
        cadrumo_declared=["shared>=1"],
        agent_declared=["agent-only"],
        cadrumo_locked={"shared": "1.0"},
        agent_locked={"shared": "2.0", "agent-only": "1.0"},
    )
    assert {name: item.version for name, item in resolved.items()} == {"shared": "2.0", "agent-only": "1.0"}
    agent = _locked(tmp_path / "index", {"shared": "2.0", "agent-only": "1.0"})
    assert {name: item.hashes for name, item in resolved.items()} == {name: item.hashes for name, item in agent.items()}


def test_served_bytes_no_lock_recorded_are_refused(tmp_path: Path) -> None:
    """A file whose hash the owning lock never recorded cannot reach the installer."""
    _wheel(tmp_path / "index", "shared", "1.0")
    with pytest.raises(DependencyGateError, match=r"serves no file of shared 1\.0 whose hash Cadrumo recorded"):
        _resolve(
            tmp_path,
            cadrumo_declared=["shared>=1"],
            agent_declared=[],
            cadrumo_locked={"shared": "1.0"},
            agent_locked={},
            recorded={"shared": ResolvedDistribution("1.0", ("f" * 64,))},
        )


def test_gate_environment_drops_every_uv_and_pip_override() -> None:
    """No index, mirror or configuration override outside the locks reaches the resolver."""
    environment = gate_environment(
        {
            "UV_INDEX_URL": "https://mirror.invalid/simple",
            "uv_extra_index_url": "https://mirror.invalid/extra",
            "PIP_INDEX_URL": "https://mirror.invalid/pip",
            "HTTPS_PROXY": "http://proxy.invalid:3128",
            "MACOSX_DEPLOYMENT_TARGET": "14.0",
        }
    )
    assert environment == {"HTTPS_PROXY": "http://proxy.invalid:3128", "MACOSX_DEPLOYMENT_TARGET": "14.0"}


def test_shared_version_from_one_lock_only_is_refused(tmp_path: Path) -> None:
    """A mixed set needs both projects' proofs, so the bundle refuses it and names the lagging repository."""
    require_single_lock_provenance({}, {"Cadrumo": tmp_path})
    with pytest.raises(DependencyGateError) as refusal:
        require_single_lock_provenance(
            {"websockets": {"selected": "16.1.1", "cadrumo": "17.2", "agent": "16.1.1"}},
            {"Cadrumo": tmp_path / "cadrumo", "cadrumo-agent": tmp_path / "cadrumo-agent"},
        )
    message = str(refusal.value)
    assert "websockets 16.1.1 (Cadrumo's lock 17.2, cadrumo-agent's lock 16.1.1)" in message
    assert "Upgrade the lagging repository" in message and "proofs" in message
    assert str(tmp_path / "cadrumo-agent") in message


def test_stricter_transitive_cap_selects_the_older_locked_version(tmp_path: Path) -> None:
    """A dependency of one project capping a shared distribution keeps the older lock's version."""
    for version in ("1.0", "2.0"):
        _wheel(tmp_path / "index", "shared", version)
    _wheel(tmp_path / "index", "capper", "1.0", ["shared<2"])
    resolved = _resolve(
        tmp_path,
        cadrumo_declared=["shared>=1"],
        agent_declared=["capper"],
        cadrumo_locked={"shared": "2.0"},
        agent_locked={"shared": "1.0", "capper": "1.0"},
    )
    assert {name: item.version for name, item in resolved.items()} == {"shared": "1.0", "capper": "1.0"}


def test_no_admissible_version_names_the_distribution_versions_and_remedy(tmp_path: Path) -> None:
    """Each locked version violating the other side's requirement is a refusal naming both repositories."""
    for version in ("1.0", "2.0"):
        _wheel(tmp_path / "index", "shared", version)
    _wheel(tmp_path / "index", "capper", "1.0", ["shared<2"])
    with pytest.raises(DependencyGateError) as refusal:
        _resolve(
            tmp_path,
            cadrumo_declared=["shared>=2"],
            agent_declared=["capper"],
            cadrumo_locked={"shared": "2.0"},
            agent_locked={"shared": "1.0", "capper": "1.0"},
        )
    message = str(refusal.value)
    assert "shared (Cadrumo's lock 2.0, cadrumo-agent's lock 1.0)" in message
    assert "capper" in message and "shared<2" in message
    assert "uv lock --upgrade" in message
    assert str(tmp_path / "cadrumo") in message and str(tmp_path / "cadrumo-agent") in message


def test_declared_requirement_refusing_both_versions_fails_before_resolving(tmp_path: Path) -> None:
    """Both versions refused by a declared requirement name the requirement each violates."""
    with pytest.raises(DependencyGateError) as refusal:
        _resolve(
            tmp_path,
            cadrumo_declared=["shared>=2"],
            agent_declared=["shared<2"],
            cadrumo_locked={"shared": "2.0"},
            agent_locked={"shared": "1.0"},
        )
    message = str(refusal.value)
    assert "Cadrumo's lock holds shared 2.0, refused because cadrumo-agent requires shared<2" in message
    assert "cadrumo-agent's lock holds shared 1.0, refused because Cadrumo requires shared>=2" in message
    assert not (tmp_path / "work").exists()


@pytest.mark.parametrize(
    ("requires_python", "behind"),
    [
        (">=3.13,<3.14", None),
        (">=3.14", "Cadrumo, whose release Python is 3.13.11"),
        (">=3.12,<3.13", "cadrumo-agent, whose pyproject.toml requires-python is >=3.12,<3.13"),
        (None, "declares no Requires-Python"),
    ],
)
def test_agent_python_must_admit_the_release_python(
    tmp_path: Path, requires_python: str | None, behind: str | None
) -> None:
    """A Python mismatch is refused with a remedy naming the side behind."""
    if behind is None:
        require_python_step_lock(requires_python, "3.13.11", tmp_path)
        return
    with pytest.raises(DependencyGateError, match=behind):
        require_python_step_lock(requires_python, "3.13.11", tmp_path)


def test_lock_export_rows_are_selected_for_the_target_environment() -> None:
    """Rows whose markers exclude the target are not part of that target's locked set."""
    export = (
        "pywin32==312 ; sys_platform == 'win32' \\\n"
        "    --hash=sha256:" + "a" * 64 + "\n"
        "uvloop==0.22.1 ; sys_platform != 'win32' \\\n"
        "    --hash=sha256:" + "b" * 64 + "\n"
        "websockets==16.1.1 \\\n"
        "    --hash=sha256:" + "c" * 64 + " \\\n"
        "    --hash=sha256:" + "d" * 64 + "\n"
    )
    assert locked_distributions(export, _WINDOWS, "export") == {
        "pywin32": ResolvedDistribution("312", ("a" * 64,)),
        "websockets": ResolvedDistribution("16.1.1", ("c" * 64, "d" * 64)),
    }
    with pytest.raises(ValueError, match="one exact version"):
        locked_distributions("websockets>=16\n", _WINDOWS, "export")
    with pytest.raises(ValueError, match="no recorded hashes"):
        locked_distributions("websockets==16.1.1\n", _WINDOWS, "export")


def test_recorded_resolution_is_refused_after_its_requirements_change(tmp_path: Path) -> None:
    """The installer reads only requirements whose digest the resolution recorded."""
    path = tmp_path / AGENT_DEPENDENCIES
    path.write_bytes(f"websockets==16.1.1 --hash=sha256:{'c' * 64}\n".encode())
    record = dict(
        target="windows-x86-64",
        python="3.13.11",
        requirements_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        versions={"websockets": "16.1.1"},
    )
    (tmp_path / AGENT_DEPENDENCY_RECORD).write_text(json.dumps(record), encoding="utf-8")
    assert set(resolved_requirements(tmp_path, "windows-x86-64", "3.13.11")) == {"websockets"}
    with pytest.raises(ValueError, match="another target"):
        resolved_requirements(tmp_path, "linux-x86-64", "3.13.11")
    path.write_bytes(f"websockets==17.2 --hash=sha256:{'c' * 64}\n".encode())
    with pytest.raises(ValueError, match="differ from their resolution record"):
        resolved_requirements(tmp_path, "windows-x86-64", "3.13.11")


@pytest.mark.parametrize("name", ["../outside.whl", "wheels/other.whl", "payload.txt"])
def test_wheel_receipt_cannot_select_another_path(tmp_path: Path, name: str) -> None:
    """An altered receipt cannot escape its declared wheel directory."""
    wheel_tree(tmp_path)
    receipt = tmp_path / "agent-wheel.json"
    record = json.loads(receipt.read_text(encoding="utf-8"))
    record["wheel"] = name
    receipt.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid agent wheel path"):
        agent_wheel(tmp_path)


def test_agent_wheel_reuses_python_inputs_independently_from_node_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    package = source / "src/cadrumo_agent"
    package.mkdir(parents=True)
    module = package / "__init__.py"
    module.write_text("value = 1\n", encoding="utf-8")
    (source / "pyproject.toml").write_text(
        '[build-system]\nrequires=["hatchling"]\nbuild-backend="hatchling.build"\n'
        '[project]\nname="cadrumo-agent"\nversion="0.1.0"\n'
        '[tool.hatch.build.targets.wheel]\npackages=["src/cadrumo_agent"]\n',
        encoding="utf-8",
    )
    node_metadata = source / "package.json"
    node_metadata.write_text('{"description":"before"}', encoding="utf-8")
    monkeypatch.delenv("UV_CACHE_DIR", raising=False)
    uv = shutil.which("uv")
    assert uv is not None
    output = tmp_path / "output"
    build_agent(output, source, uv)
    wheel = agent_wheel(output)
    before = wheel.stat().st_mtime_ns

    node_metadata.write_text('{"description":"after"}', encoding="utf-8")
    build_agent(output, source, uv)
    assert wheel.stat().st_mtime_ns == before

    module.write_text("value = 2\n", encoding="utf-8")
    build_agent(output, source, uv)
    assert wheel.stat().st_mtime_ns != before
