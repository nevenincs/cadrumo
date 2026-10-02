"""Installed TUI module and child-process entrypoint checks."""

from __future__ import annotations

import asyncio
import json
import runpy
import sys
from pathlib import Path

import pytest

from ....adapters.local_runtime.framing import RuntimeTransportCleanup
from ....adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from ....tests.audited_process import run_audited_process
from .. import launcher
from ..launcher import main

pytestmark = [pytest.mark.hex_entrypoint]

_CLI_PACKAGE = "cadrumo.entrypoints.cli"
_CHILD_IMPORT_PROBE = """\
import json
import sys

for module in sys.argv[1:]:
    __import__(module)
print(json.dumps(sorted(name for name in sys.modules if name == {cli!r} or name.startswith({cli!r} + "."))))
"""


def _cli_modules_a_fresh_process_loads(*modules: str) -> list[str]:
    """Import ``modules`` in a new interpreter and return the CLI modules it then holds.

    The question is what the CHILD process loads, so it is asked of a child. This
    test process has usually imported CLI test modules already, so its own
    ``sys.modules`` answers for whatever ran first, not for the code under test.
    """
    completed = run_audited_process(
        [sys.executable, "-c", _CHILD_IMPORT_PROBE.format(cli=_CLI_PACKAGE), *modules],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=300,
    )
    assert completed.returncode == 0, str(completed.stderr)[-4000:]
    loaded = json.loads(str(completed.stdout).strip().splitlines()[-1])
    assert isinstance(loaded, list)
    return [str(name) for name in loaded]


@pytest.mark.hex_entrypoint
@pytest.mark.integration
def test_the_installed_session_never_pulls_the_cli_into_the_child_process() -> None:
    """Composing the whole workbench must not import the sibling entrypoint.

    The boundary is out-of-process by decision, and an import is exactly how
    it would stop being one. This checks the modules actually loaded rather
    than a source-level grep, so an import reached through a function body is
    still caught, and it checks them in a fresh interpreter running the
    child's own entry modules, so test order cannot change the verdict.
    """
    child_modules = ("cadrumo.entrypoints.tui.launcher", "cadrumo.entrypoints.tui.installed_session")

    assert _cli_modules_a_fresh_process_loads(*child_modules) == []


@pytest.mark.integration
def test_the_child_import_probe_reports_a_cli_import_when_one_happens() -> None:
    """The control: the same probe, handed a CLI module, reports it.

    Without this an interpreter that failed to import anything, or a filter
    that matched nothing, would pass the test above for the wrong reason.
    """
    assert _CLI_PACKAGE + ".main" in _cli_modules_a_fresh_process_loads(_CLI_PACKAGE + ".main")


@pytest.mark.hex_entrypoint
@pytest.mark.integration
def test_an_empty_profile_store_ends_the_headless_session_without_creating_one(tmp_path: Path) -> None:
    """The artifact proves it starts without inventing an operator's profile.

    ``--self-test`` exists to show the installed surface composes. It must not
    register a profile as a side effect of that proof, and it must not sit
    waiting for credentials nobody is there to type.
    """
    from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
    from ..installed_session import SESSION_COMPLETED

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        assert main(headless=True) == SESSION_COMPLETED
        assert not list(Path(storage_root).glob("**/*.capsule"))


@pytest.mark.unit
@pytest.mark.parametrize("kind", ["cleanup", "runtime", "frontend"])
def test_module_cleanup_refusal_exits_without_disclosing_native_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    sentinel = "UNIQUE-SYNTHETIC-NATIVE-CLOSE-FAILURE-DO-NOT-DISCLOSE"

    class NativeRelease:
        def close(self) -> None:
            raise OSError(sentinel)

    owner = RuntimeTransportCleanup(NativeRelease())

    async def fail_cleanup() -> None:
        await close_async_resources(owner, task_name="tui-module-fault", primary_error=None)

    with pytest.raises(AsyncResourceCleanupError) as retained:
        asyncio.run(fail_cleanup())
    primary = (
        RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if kind == "runtime"
        else RuntimeFrontendRefusedError("authentication_required")
        if kind == "frontend"
        else retained.value
    )
    if not isinstance(primary, AsyncResourceCleanupError):
        primary.__dict__["async_cleanup_error"] = retained.value

    def refuse_module(_arguments: list[str]) -> int:
        raise primary

    monkeypatch.setattr(launcher, "run_module", refuse_module)
    monkeypatch.setattr(sys, "argv", ["cadrumo-tui"])
    monkeypatch.setenv("PYDANTIC_DISABLE_PLUGINS", "__all__")
    with pytest.raises(SystemExit) as exited:
        runpy.run_module("cadrumo.entrypoints.tui", run_name="__main__", alter_sys=False)
    assert exited.value.code == 1
    output = capsys.readouterr()
    assert output.out == "" and output.err.strip() == "runtime_cleanup_incomplete"
    assert sentinel not in output.out + output.err
