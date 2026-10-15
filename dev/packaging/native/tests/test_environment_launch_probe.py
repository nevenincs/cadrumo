"""The launch probe's logic, exercised against a stand-in host and agent until a bundle exists to run it on."""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import psutil
import pytest

from dev._paths import REPO_ROOT

from .stand_in_launch import StandIn, build, generated_contract, host_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TARGET = {"win32": "windows-x86-64", "darwin": "macos-arm64"}.get(sys.platform, "linux-x86-64")


def _load_probe() -> ModuleType:
    path = REPO_ROOT / "native" / "tests" / "environment_launch_probe.py"
    spec = importlib.util.spec_from_file_location("environment_launch_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe = _load_probe()


@pytest.fixture(scope="module")
def contract_document(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return generated_contract(tmp_path_factory.mktemp("generated"), _TARGET)


@pytest.fixture
def stand_in(tmp_path: Path, contract_document: dict[str, Any]) -> StandIn:
    return build(tmp_path, _TARGET, copy.deepcopy(contract_document))


def _names(stand_in: StandIn) -> Any:
    fields = {"worker_port", "gateway_url", "worker_host", "gateway_lifetime_id", "worker_generation"}
    return probe.AgentNames(**{field: name for field, name in stand_in.agent_names.items() if field in fields})


def _launcher(stand_in: StandIn, children: Any = None) -> Any:
    return probe.Launcher(
        image=lambda path, arguments: host_command(stand_in, path.stem, list(arguments)),
        python=lambda arguments: host_command(stand_in, "python", list(arguments)),
        children=children or (lambda pid: []),
    )


def _checks(stand_in: StandIn, tmp_path: Path, *, children: Any = None, timeout: float = 120.0) -> Any:
    work = Path(tempfile.mkdtemp(dir=tmp_path))
    return probe.Probe(
        probe.read_contract(stand_in.package, stand_in.contract),
        _names(stand_in),
        _launcher(stand_in, children),
        work,
        timeout=timeout,
        worker_wait=2.0,
    )


def _run(stand_in: StandIn, **options: Any) -> list[Any]:
    return asyncio.run(
        probe.run_probe(
            stand_in.package,
            stand_in.contract,
            launcher=_launcher(stand_in, options.pop("children", None)),
            names=_names(stand_in),
            **options,
        )
    )


def _worker_child(stand_in: StandIn) -> Any:
    contract = probe.read_contract(stand_in.package, stand_in.contract)
    return lambda pid: [(str(contract.image_path), contract.worker_arguments)]


def _failure(stand_in: StandIn, tmp_path: Path, check: str, **options: Any) -> str:
    checks = _checks(stand_in, tmp_path, **options)
    with pytest.raises(probe.ProbeFailedError) as raised:
        asyncio.run(getattr(checks, check)())
    return str(raised.value)


def test_every_check_holds_for_a_host_that_defines_each_environment_from_the_declaration(stand_in: StandIn) -> None:
    results = _run(stand_in)
    assert [(result.name, result.failure) for result in results] == [
        ("undeclared invocation", None),
        ("agent stores", None),
        ("hosted gateway", None),
        ("worker", None),
        ("generic interpreter", None),
    ]
    assert "setup succeeded; stores-state reads current" in results[1].detail
    gateway = results[2]
    assert "refused hosted_lane_unproven" in gateway.detail
    assert gateway.pending and "agent_ready" in gateway.pending[0]
    assert all(not result.pending for result in results if result is not gateway)


def test_a_gateway_that_proves_its_tool_server_reports_ready_and_re_executes_the_image_for_its_worker(
    stand_in: StandIn, tmp_path: Path
) -> None:
    stand_in.agent_mode("ready")
    result = asyncio.run(_checks(stand_in, tmp_path, children=_worker_child(stand_in)).gateway())
    assert result.failure is None and result.pending == ()
    assert "agent_ready" in result.detail


def test_a_ready_gateway_whose_worker_is_not_the_agent_image_is_found(stand_in: StandIn, tmp_path: Path) -> None:
    stand_in.agent_mode("ready")

    def elsewhere(pid: int) -> list[tuple[str, tuple[str, ...]]]:
        return [(sys.executable, ("-m", "elsewhere"))]

    message = _failure(stand_in, tmp_path, "gateway", children=elsewhere)
    assert "no process the gateway started is the agent image" in message
    assert "sys.frozen" in message


@pytest.mark.parametrize(
    ("mode", "fragment"),
    [
        pytest.param("no_setup", "stores-state reads 'absent' after setup", id="stores-not-set-up"),
        pytest.param("setup_fails", "setup did not succeed", id="setup-fails"),
        pytest.param("stores_mismatch", "hosted_stores_mismatch", id="stores-the-gateway-refuses"),
        pytest.param("proof_policy", "hosted_proof_policy", id="proof-policy"),
    ],
)
def test_an_earlier_refusal_is_a_set_up_error_and_says_so(
    stand_in: StandIn, tmp_path: Path, mode: str, fragment: str
) -> None:
    stand_in.agent_mode(mode)
    checks = _checks(stand_in, tmp_path)
    with pytest.raises(probe.SetupError, match=fragment):
        asyncio.run(checks.gateway())


def test_a_set_up_error_is_reported_as_one(stand_in: StandIn) -> None:
    stand_in.agent_mode("no_setup")
    gateway = next(result for result in _run(stand_in) if result.name == "hosted gateway")
    assert gateway.failure is not None and gateway.failure.startswith("set-up error: ")


def test_the_stores_check_runs_the_images_own_invocations_in_the_gateways_environment(
    stand_in: StandIn, tmp_path: Path
) -> None:
    checks = _checks(stand_in, tmp_path)
    result = asyncio.run(checks.stores())
    assert result.failure is None
    assert "stores-state answered 'absent'; setup succeeded; stores-state reads current" in result.detail
    # The stand-in agent records the stores only for the hosted root the host gave it.
    assert (checks.hosted / "stores.marker").read_text(encoding="utf-8") == "current"
    assert asyncio.run(checks.stores()) is result, "the sequence runs once"


def test_a_failing_stores_step_fails_its_own_check_and_is_a_set_up_error_for_the_gateway(stand_in: StandIn) -> None:
    stand_in.agent_mode("no_setup")
    results = {result.name: result for result in _run(stand_in)}
    stores = results["agent stores"].failure
    assert stores is not None and "stores-state reads 'absent' after setup" in stores
    assert not stores.startswith("set-up error: ")
    gateway = results["hosted gateway"].failure
    assert gateway is not None and gateway.startswith(
        "set-up error: the hosted root's stores could not be made current"
    )


def test_a_stores_state_that_names_no_state_is_found(stand_in: StandIn, tmp_path: Path) -> None:
    stand_in.agent_mode("garbled_state")
    assert "stores-state did not answer with a state" in _failure(stand_in, tmp_path, "stores")


def test_a_host_refusal_of_a_store_invocation_names_the_native_code_and_subject(
    stand_in: StandIn, tmp_path: Path
) -> None:
    stand_in.host_faults(refuse=["invocation_undeclared", "cadrumo-agent"])
    message = _failure(stand_in, tmp_path, "stores")
    assert (
        "the host refused the stores-state launch before Python started: invocation_undeclared (cadrumo-agent)"
        in message
    )


def test_a_gateway_that_dies_without_a_line_is_reported_with_its_status(stand_in: StandIn, tmp_path: Path) -> None:
    stand_in.agent_mode("crash")
    assert "ended with status 1" in _failure(stand_in, tmp_path, "gateway")


def test_a_gateway_that_never_answers_is_stopped_at_the_timeout_and_killed(stand_in: StandIn, tmp_path: Path) -> None:
    stand_in.agent_mode("hang")
    checks = _checks(stand_in, tmp_path)
    asyncio.run(checks.stores())
    checks.timeout = 8.0
    started = time.monotonic()
    with pytest.raises(probe.ProbeFailedError) as raised:
        asyncio.run(checks.gateway())
    message = str(raised.value)
    assert "no protocol line before the timeout" in message
    assert time.monotonic() - started < 60
    pid = stand_in.gateway_pid()
    assert pid is not None, "the gateway never started, so nothing was proven about killing it"
    deadline = time.monotonic() + 15
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not psutil.pid_exists(pid)


def test_a_host_refusal_of_the_gateway_and_the_worker_names_the_native_code_and_subject(
    stand_in: StandIn, tmp_path: Path
) -> None:
    # Only the gateway's own launch is refused, so its stores step still succeeds.
    stand_in.host_faults(refuse=["launch_value_malformed", "SOME_VARIABLE"], only="serve")
    expected = "the host refused the {kind} launch before Python started: launch_value_malformed (SOME_VARIABLE)"
    assert expected.format(kind="gateway") in _failure(stand_in, tmp_path, "gateway")
    stand_in.host_faults(refuse=["launch_value_malformed", "SOME_VARIABLE"])
    assert "launch_value_malformed (SOME_VARIABLE)" in _failure(stand_in, tmp_path, "worker")


def test_a_worker_that_is_not_given_its_settings_does_not_report_a_port(stand_in: StandIn, tmp_path: Path) -> None:
    stand_in.agent_mode("hang")
    assert "did not report the port it bound" in _failure(stand_in, tmp_path, "worker", timeout=8.0)


def test_an_image_that_admits_an_undeclared_invocation_is_found(stand_in: StandIn, tmp_path: Path) -> None:
    stand_in.host_faults(admit_all=True)
    assert "the image exited 0, not 125" in _failure(stand_in, tmp_path, "undeclared_invocation")


def test_a_refusal_line_that_is_not_exactly_the_one_declared_is_found(stand_in: StandIn, tmp_path: Path) -> None:
    stand_in.host_faults(spaced_json=True)
    message = _failure(stand_in, tmp_path, "undeclared_invocation")
    assert 'expected exactly {"native_refusal":"invocation_undeclared","subject":"cadrumo-agent"}' in message


@pytest.mark.parametrize(
    ("fault", "fragment"),
    [
        pytest.param({"path": "elsewhere"}, "is not the declared composition", id="path"),
        pytest.param({"root": "elsewhere"}, "is not the command line's default", id="root"),
    ],
)
def test_a_generic_interpreter_that_breaks_its_profile_is_found(
    stand_in: StandIn, tmp_path: Path, fault: dict[str, str], fragment: str
) -> None:
    stand_in.host_faults(**fault)
    assert fragment in _failure(stand_in, tmp_path, "python_image")


def test_a_generic_interpreter_that_lets_an_agent_name_through_is_found(stand_in: StandIn, tmp_path: Path) -> None:
    contract = probe.read_contract(stand_in.package, stand_in.contract)
    leaked = sorted(contract.agent_only_names)[:1]
    stand_in.host_faults(leak=leaked)
    message = _failure(stand_in, tmp_path, "python_image")
    assert "let agent-only names through" in message and leaked[0] in message


def test_the_agent_only_names_are_the_ones_no_other_image_admits(stand_in: StandIn) -> None:
    contract = probe.read_contract(stand_in.package, stand_in.contract)
    declared = stand_in.contract["application_environment"]
    root = stand_in.contract["root"]["variable"]
    assert stand_in.agent_names["hosted_root"] in contract.agent_only_names
    # A name only the agent's prefix admits is planted too, so a host that lists names is caught.
    prefix = contract.gateway["prefix"]
    assert prefix and any(
        name.startswith(prefix) and name not in declared["names"] for name in contract.agent_only_names
    )
    assert contract.worker["prefix"] == prefix
    assert root not in contract.agent_only_names
    assert not contract.agent_only_names & set(declared["pins"]["temporary"])
    for profile in declared["profiles"]:
        if profile["image"] != contract.image_name:
            assert not contract.agent_only_names & {*profile["operator"], *profile["pass"]}, profile["name"]


def test_the_agent_image_and_the_runtime_relay_are_read_from_the_contract(stand_in: StandIn) -> None:
    contract = probe.read_contract(stand_in.package, stand_in.contract)
    suffix = stand_in.contract["layout"]["entrypoint_suffix"]
    assert contract.image_path == stand_in.package / "bin" / f"cadrumo-agent{suffix}"
    assert contract.relay_path == stand_in.package / "bin" / f"cadrumo-mcp{suffix}"
    assert contract.aeat_path == stand_in.package / "bin" / f"aeat{suffix}"
    assert contract.python_path == stand_in.package / stand_in.contract["layout"]["paths"]["executable"]
    # The agent refuses a declared program inside a virtual environment: no folder from the interpreter up
    # to the package root holds a pyvenv.cfg, and the layout stages none.
    folder = contract.python_path.parent
    while True:
        assert not (folder / "pyvenv.cfg").exists()
        if folder == stand_in.package:
            break
        folder = folder.parent
    assert "pyvenv.cfg" not in json.dumps(stand_in.contract["layout"])
    assert contract.worker_arguments == ("-m", "cadrumo_agent.worker")
    assert contract.stores_state_arguments == ("-m", "cadrumo_agent.cli.main", "stores-state")
    assert contract.setup_arguments == ("-m", "cadrumo_agent.cli.main", "setup")
    assert contract.gateway["name"] != contract.worker["name"]


def test_a_contract_the_probe_cannot_read_is_a_set_up_error(stand_in: StandIn) -> None:
    two = copy.deepcopy(stand_in.contract)
    two["layout"]["bundled_images"]["another"] = {}
    with pytest.raises(probe.SetupError, match="bundled images"):
        probe.read_contract(stand_in.package, two)
    other = copy.deepcopy(stand_in.contract)
    invocation = next(
        item for item in other["application_environment"]["invocations"] if item["image"] == "cadrumo-agent"
    )
    invocation["arguments"][1] = {"literal": "elsewhere"}
    invocation["arguments"][2] = {"literal": "elsewhere"}
    with pytest.raises(probe.SetupError, match="not one gateway invocation"):
        probe.read_contract(stand_in.package, other)
    # A store invocation the package does not declare, or declares outside the gateway's profile, is found.
    for verb in ("stores-state", "setup"):
        without = copy.deepcopy(stand_in.contract)
        invocations = without["application_environment"]["invocations"]
        invocations[:] = [item for item in invocations if item["arguments"][-1] != {"literal": verb}]
        with pytest.raises(probe.SetupError, match="does not declare"):
            probe.read_contract(stand_in.package, without)
        elsewhere = copy.deepcopy(stand_in.contract)
        selected = next(
            item
            for item in elsewhere["application_environment"]["invocations"]
            if item["arguments"][-1] == {"literal": verb}
        )
        selected["profile"] = "agent-worker"
        with pytest.raises(probe.SetupError):
            probe.read_contract(stand_in.package, elsewhere)


@pytest.mark.parametrize(
    ("line", "status", "standard_error", "verdict"),
    [
        pytest.param(b'{"event":"agent_ready","gateway_port":1}\n', None, b"", "ready", id="ready"),
        pytest.param(b'{"event":"refused","code":"hosted_lane_unproven"}\n', None, b"", "unproven", id="unproven"),
    ],
)
def test_the_gateway_lines_the_probe_accepts(
    line: bytes, status: int | None, standard_error: bytes, verdict: str
) -> None:
    assert probe.classify_gateway(line, status, standard_error) == verdict


@pytest.mark.parametrize(
    ("line", "status", "standard_error", "error", "fragment"),
    [
        pytest.param(None, None, b"", probe.ProbeFailedError, "no protocol line before the timeout", id="silent"),
        pytest.param(
            b"", 1, b"Traceback\nboom\n", probe.ProbeFailedError, "status 1 and wrote no protocol line", id="ended"
        ),
        pytest.param(
            b"",
            125,
            b'{"native_refusal":"launch_value_missing","subject":"A_NAME"}\n',
            probe.ProbeFailedError,
            "launch_value_missing (A_NAME)",
            id="host-refused",
        ),
        pytest.param(b"not json\n", None, b"", probe.ProbeFailedError, "not JSON", id="not-json"),
        pytest.param(
            b'{"event":"other"}\n', None, b"", probe.ProbeFailedError, "neither agent_ready", id="other-event"
        ),
        pytest.param(
            b'{"event":"refused","code":"x"}\n', None, b"", probe.ProbeFailedError, "which is not", id="other-refusal"
        ),
        pytest.param(
            b'{"event":"refused","code":"hosted_stores_mismatch"}\n', None, b"", probe.SetupError, "stores", id="stores"
        ),
        pytest.param(
            b'{"event":"refused","code":"hosted_credential_frame"}\n', None, b"", probe.SetupError, "frame", id="frame"
        ),
    ],
)
def test_the_gateway_lines_the_probe_refuses(
    line: bytes | None, status: int | None, standard_error: bytes, error: type[Exception], fragment: str
) -> None:
    with pytest.raises(error, match=re.escape(fragment)):
        probe.classify_gateway(line, status, standard_error)


def test_a_worker_is_the_agent_image_run_with_exactly_the_worker_invocation() -> None:
    image = Path(sys.executable)
    arguments = ("-m", "cadrumo_agent.worker")
    probe.check_worker_reexecution([("elsewhere", ()), (str(image), arguments)], image, arguments)
    for children in ([], [(str(image), ("run-module", "cadrumo_agent.worker"))], [("elsewhere", arguments)]):
        with pytest.raises(probe.ProbeFailedError, match="no process the gateway started"):
            probe.check_worker_reexecution(children, image, arguments)


def test_the_declared_path_is_the_packages_directories_then_the_systems(stand_in: StandIn) -> None:
    contract = probe.read_contract(stand_in.package, stand_in.contract)
    package = str(stand_in.package)
    if sys.platform == "win32":
        system = [str(Path(r"C:\Windows", "System32"))]
        environment = {"SystemRoot": r"C:\Windows"}
    else:
        system = ["/usr/bin", "/bin"]
        environment = {}
    assert probe.declared_path(contract, environment) == [package, str(stand_in.package / "bin"), *system]
    external = os.pathsep.join(["first", "second"])
    relocated = probe.declared_path(contract, {**environment, "CADRUMO_EXTERNAL_BIN_DIRS": external})
    assert relocated == [package, "first", "second", str(stand_in.package / "bin"), *system]


def test_a_program_that_outlives_its_timeout_is_killed_with_what_it_started(tmp_path: Path) -> None:
    marker = tmp_path / "child.pid"
    child = "import time; time.sleep(600)"
    parent = (
        "import pathlib, subprocess, sys, time\n"
        f"p = subprocess.Popen([sys.executable, '-c', {child!r}])\n"
        f"pathlib.Path({str(marker)!r}).write_text(str(p.pid))\n"
        "time.sleep(600)\n"
    )
    with pytest.raises(probe.ProbeFailedError, match="did not end within 8 s and was killed"):
        asyncio.run(probe.run_to_end([sys.executable, "-c", parent], os.environ, cwd=tmp_path, timeout=8.0))
    assert marker.is_file(), "the program never started its child"
    pid = int(marker.read_text())
    deadline = time.monotonic() + 15
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not psutil.pid_exists(pid)


def test_the_process_tree_lists_every_descendant_with_its_program_and_arguments(tmp_path: Path) -> None:
    child = "import time; time.sleep(600)"
    parent = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(600)"

    async def inspect() -> list[Any]:
        running = await probe.Running.start([sys.executable, "-c", parent], os.environ, stdin=b"", cwd=tmp_path)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                tree = list(probe.process_tree(running.pid))
                if any(arguments == ("-c", child) for _, arguments in tree):
                    return tree
                await asyncio.sleep(0.2)
            return list(probe.process_tree(running.pid))
        finally:
            await running.kill()

    tree = asyncio.run(inspect())
    assert any(arguments == ("-c", child) for _, arguments in tree), tree


def test_the_probe_prints_each_check_and_exits_one_when_a_check_fails(
    stand_in: StandIn, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(stand_in.contract), encoding="utf-8")
    names = _names(stand_in)
    arguments = [str(stand_in.package), str(contract_path)]
    assert probe.main(arguments, launcher=_launcher(stand_in), names=names) == 0
    printed = capsys.readouterr().out.splitlines()
    assert [line.split(":")[0] for line in printed if not line.startswith(" ")] == [
        "ok   undeclared invocation",
        "ok   agent stores",
        "ok   hosted gateway",
        "ok   worker",
        "ok   generic interpreter",
    ]
    assert any(line.strip().startswith("pending: agent_ready") for line in printed)
    stand_in.agent_mode("crash")
    assert probe.main(arguments, launcher=_launcher(stand_in), names=names) == 1
    assert "FAIL hosted gateway: the gateway ended with status 1" in capsys.readouterr().out
