"""Exercise the private wheel's source identity and checksum admission."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from .. import agent
from ..agent import agent_wheel, build_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


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


def test_lock_generation_writes_a_candidate_without_replacing_the_authored_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text('[project]\ndependencies=["native-example==1.0"]\n')
    build = tmp_path / "build"
    inputs = build / "agent"
    inputs.mkdir(parents=True)
    (inputs / "agent-wheel.json").write_text(json.dumps({"source": str(source)}))
    generated = build / "generated"
    generated.mkdir()
    (generated / "build-toolchain.json").write_text("{}")
    (build / "build-paths.json").write_text(
        json.dumps({"paths": {"agent": "agent", "generated": "generated", "testing": "testing"}})
    )
    monkeypatch.setattr(agent, "selected_uv", lambda _configured: "uv")
    monkeypatch.setattr(agent, "export_runtime_constraints", lambda **_kwargs: ())
    authored = agent.REPO_ROOT / "native/agent/windows-x86-64.txt"
    before = authored.read_bytes()

    def resolve(command: list[str], **_kwargs: object) -> SimpleNamespace:
        output = Path(command[command.index("--output-file") + 1])
        assert output == build / "testing/agent-lock/windows-x86-64/requirements.txt"
        output.write_text("native-example==1.0 --hash=sha256:" + "a" * 64 + "\n")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(agent, "run_command", resolve)
    agent.update_lock(build, "windows-x86-64")
    assert authored.read_bytes() == before
    assert (build / "testing/agent-lock/windows-x86-64/requirements.txt").is_file()


@pytest.mark.parametrize("target", ["../../outside", r"..\..\outside", "/outside", "unknown-target"])
def test_lock_generation_refuses_unenrolled_target_before_writing(tmp_path: Path, target: str) -> None:
    with pytest.raises(ValueError, match="Unsupported distribution target"):
        agent.update_lock(tmp_path, target)
    assert not list(tmp_path.iterdir())


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
