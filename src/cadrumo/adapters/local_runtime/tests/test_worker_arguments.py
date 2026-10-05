"""Host-selected isolated worker argv, shared by every POSIX guardian."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from ..worker_arguments import validated_worker_arguments

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_INSTALLED = ("-I", "-m", "cadrumo.entrypoints.runtime.worker")


def test_installed_worker_prefix_and_its_complete_command_are_accepted() -> None:
    assert validated_worker_arguments() == _INSTALLED
    command = (*_INSTALLED, "--worker-id", "w")
    assert validated_worker_arguments(command) == command


def test_selected_script_replaces_the_installed_module(tmp_path: Path) -> None:
    script = tmp_path / "worker.py"
    script.write_text("# synthetic trusted host entrypoint\n", encoding="ascii")
    selected = ("-I", str(script.resolve(strict=True)))
    assert validated_worker_arguments(worker_script=script) == selected
    assert validated_worker_arguments((*selected, "--x"), worker_script=script) == (*selected, "--x")
    with pytest.raises(RuntimeRefusalError):
        validated_worker_arguments(_INSTALLED, worker_script=script)


@pytest.mark.parametrize(
    "command",
    [("-I", "-m", "other.worker"), ("-m", "cadrumo.entrypoints.runtime.worker"), (*_INSTALLED, "bad\0argument"), ()],
)
def test_substituted_module_dropped_isolation_or_nul_refuses(command: tuple[str, ...]) -> None:
    with pytest.raises(RuntimeRefusalError) as caught:
        validated_worker_arguments(command)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


@pytest.mark.parametrize("invalid", ["relative", "missing", "directory"])
def test_unusable_selected_script_refuses(tmp_path: Path, invalid: str) -> None:
    script = {"relative": Path("worker.py"), "missing": tmp_path / "missing.py", "directory": tmp_path}[invalid]
    with pytest.raises(RuntimeRefusalError) as caught:
        validated_worker_arguments(worker_script=script)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
