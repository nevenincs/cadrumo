"""Launch the bundled agent image as the runtime does and prove the package defined each image's environment.

Run by the assembled package's own interpreter::

    python environment_launch_probe.py <package root> <generated contract.json>

The probe starts programs from the package, never from a checkout:

* The agent image, given an invocation its launch profiles do not declare, exits with the native host's
  launch-profile status after writing the one refusal line the runtime reads.
* The agent image's own store invocations, run in the environment the runtime composes for the gateway,
  bring a synthetic hosted root to ``current``: ``stores-state`` answers, ``setup`` succeeds, and
  ``stores-state`` then reads ``current``.
* The agent gateway, started through the runtime's own composer with a hosted environment in that root and
  the runtime's own empty credential frame, answers on the hosting protocol. Until the agent records
  a proof of its hosted lane, the answer is the refusal ``hosted_lane_unproven``, which also proves the
  gateway received its hosted root. Once a lane proof exists the answer is ``agent_ready``.
* The agent worker, started through the image's worker invocation, reports the port it bound.
* The generic interpreter image clears every name only the agent image admits, sets the declared ``PATH``
  and pins the storage root to the command line's own built-in default.

An earlier refusal of the gateway (the stores, the proof policy, the frame) means the probe's set-up is wrong
and is reported as such. Every program started has a hard timeout and is killed with its whole tree.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import os
import secrets
import shutil
import signal
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from cadrumo.adapters.local_runtime.agent_programs import (
    GATEWAY_ARGUMENTS,
    PACKAGE_AGENT_VARIABLE,
    PACKAGE_RELAY_VARIABLE,
)
from cadrumo.application.agent_host.credential_frame import build_credential_frame
from cadrumo.application.agent_host.launch_environment import agent_launch_environment
from cadrumo.application.agent_host.native_refusal import NativeLaunchRefusalCode, native_launch_refusal_from

FIRST_LINE_SECONDS: Final = 180.0
"""How long a started program may take to write its first protocol line."""
STOP_SECONDS: Final = 20.0
WORKER_WAIT_SECONDS: Final = 15.0
"""How long a ready gateway may take to show its worker running."""
"""How long a program may take to end after its standard input closes, before it is killed."""
_STANDARD_ERROR_BYTES: Final = 8192
_UNPROVEN: Final = "hosted_lane_unproven"
_UNDECLARED_ARGUMENTS: Final = ("-c", "pass")
_SETUP_ADVICE: Final = {
    "hosted_stores_mismatch": "the image's setup invocation left stores the gateway still refuses",
    "hosted_proof_policy": "the proof policy reaching the gateway is not the one a hosted root takes",
    "hosted_settings_file": "a settings file reached the gateway beside the hosted root",
    "hosted_terminal_program": "a retired program setting reached the gateway",
    "hosted_tracing": "tracing reached the gateway's environment",
    "hosted_credential_frame": "the credential frame the runtime builds was not accepted",
    "hosted_credential_environment": "a credential reached the gateway's environment",
    "hosted_bind_failed": "the gateway could not bind its listening port",
    "hosted_start_failed": "the gateway stopped before it reported ready",
}
_STORE_VERBS: Final = ("stores-state", "setup")
_STORES_STATES: Final = frozenset({"absent", "older", "current", "newer"})
_SETUP_STATUSES: Final = frozenset({"succeeded", "already-initialized"})
_REPORT_PROGRAM: Final = (
    "import json, os\n"
    "from cadrumo.core.storage_environment import host_installed_default_root\n"
    "print(json.dumps({'environment': dict(os.environ), 'default': str(host_installed_default_root(os.environ))}))\n"
)


class ProbeFailedError(Exception):
    """A check the probe makes does not hold; carries the sentence that says which and why."""


class SetupError(ProbeFailedError):
    """The probe's own set-up is wrong, so the check could not be made."""


@dataclass(frozen=True)
class AgentNames:
    """The environment names the agent reads for the settings the probe supplies, as the agent spells them."""

    worker_port: str
    gateway_url: str
    worker_host: str
    gateway_lifetime_id: str
    worker_generation: str

    @classmethod
    def from_resolver(cls, resolve: Callable[[str], str]) -> AgentNames:
        """Ask the agent for the name of each setting; it is the only place that spells them."""
        return cls(
            worker_port=resolve("worker_port"),
            gateway_url=resolve("gateway_url"),
            worker_host=resolve("worker_host"),
            gateway_lifetime_id=resolve("gateway_lifetime_id"),
            worker_generation=resolve("worker_generation"),
        )


def installed_agent_names() -> AgentNames:
    """Read the setting names from the bundled agent installed beside this interpreter."""
    # Imported by name: the agent is installed in the package's interpreter, which is not the one that checks this file.
    config = importlib.import_module("cadrumo_agent.control.config")
    return AgentNames.from_resolver(config.setting_env)


def process_tree(pid: int) -> list[tuple[str, tuple[str, ...]]]:
    """List the program and arguments of every process the process ``pid`` started, directly or not."""
    import psutil

    children: list[tuple[str, tuple[str, ...]]] = []
    for child in psutil.Process(pid).children(recursive=True):
        with contextlib.suppress(psutil.Error):
            children.append((str(child.exe()), tuple(str(argument) for argument in child.cmdline()[1:])))
    return children


@dataclass(frozen=True)
class Launcher:
    """How the probe starts programs. The package's images run directly; a test substitutes its own."""

    image: Callable[[Path, Sequence[str]], list[str]] = lambda path, arguments: [str(path), *arguments]
    python: Callable[[Sequence[str]], list[str]] = lambda arguments: [sys.executable, *arguments]
    children: Callable[[int], list[tuple[str, tuple[str, ...]]]] = process_tree


@dataclass(frozen=True)
class Contract:
    """The parts of the generated contract the probe reads: the package's own declaration."""

    package: Path
    document: Mapping[str, Any]
    image_name: str
    image_path: Path
    relay_path: Path
    gateway: Mapping[str, Any]
    worker: Mapping[str, Any]
    worker_arguments: tuple[str, ...]
    stores_state_arguments: tuple[str, ...]
    setup_arguments: tuple[str, ...]
    agent_only_names: frozenset[str]

    @property
    def section(self) -> Mapping[str, Any]:
        """The compiled environment declaration."""
        section: Mapping[str, Any] = self.document["application_environment"]
        return section

    @property
    def windows(self) -> bool:
        """Whether the target's environment names compare without case."""
        return str(self.section["platform_family"]) == "windows"


def _literals(invocation: Mapping[str, Any]) -> tuple[str | None, ...]:
    literals = (argument.get("literal") for argument in invocation["arguments"])
    return tuple(None if literal is None else str(literal) for literal in literals)


def read_contract(package: Path, document: Mapping[str, Any]) -> Contract:
    """Resolve the agent image, its gateway and worker profiles, its store invocations and the runtime's relay."""
    layout, section = document["layout"], document["application_environment"]
    bundled = list(layout["bundled_images"])
    if len(bundled) != 1:
        raise SetupError(f"the package declares {len(bundled)} bundled images; the probe expects one: {bundled}")
    name = bundled[0]
    native, suffix = package / layout["paths"]["native"], layout["entrypoint_suffix"]
    profiles = {profile["name"]: profile for profile in section["profiles"]}
    own = [profile for profile in profiles.values() if profile["image"] == name]
    invocations = [
        (str(invocation["profile"]), _literals(invocation))
        for invocation in section["invocations"]
        if invocation["image"] == name
    ]
    gateways = {profile for profile, literals in invocations if literals == tuple(GATEWAY_ARGUMENTS)}
    workers = {profile["name"] for profile in own} - gateways
    if len(gateways) != 1 or len(workers) != 1:
        selected = {
            profile["name"]: [lit for chosen, lit in invocations if chosen == profile["name"]] for profile in own
        }
        raise SetupError(
            f"the package's {name} profiles are not one gateway invocation {list(GATEWAY_ARGUMENTS)} and one other: "
            f"{selected}"
        )
    gateway_name, worker_name = next(iter(gateways)), next(iter(workers))
    worker_arguments = [literals for chosen, literals in invocations if chosen == worker_name]
    if len(worker_arguments) != 1 or any(argument is None for argument in worker_arguments[0]):
        raise SetupError(
            "the worker profile is not selected by one invocation of literal arguments the probe can spell"
        )
    # The store invocations run in the gateway's environment, so they must select the gateway's profile.
    stores = {}
    for verb in _STORE_VERBS:
        arguments = (*GATEWAY_ARGUMENTS[:-1], verb)
        if (gateway_name, arguments) not in invocations:
            raise SetupError(f"the package's {name} image does not declare {list(arguments)} in the gateway's profile")
        stores[verb] = arguments
    fixed = {value["name"]: value for profile in profiles.values() for value in profile["fixed"]}
    relay = fixed.get(PACKAGE_RELAY_VARIABLE)
    agent = fixed.get(PACKAGE_AGENT_VARIABLE)
    if relay is None or relay["source"] != "image" or agent is None or agent["value"] != name:
        raise SetupError("the runtime's profile does not fix the agent image and the relay image")

    def admitted(profile: Mapping[str, Any]) -> set[str]:
        return {*profile["operator"], *profile["pass"], *(slot["name"] for slot in profile["slots"])}

    others = set().union(*(admitted(profile) for profile in profiles.values() if profile["image"] != name))
    pinned = {document["root"]["variable"], section["pins"]["authority"]["name"], *section["pins"]["temporary"]}
    agent_only = set().union(*(admitted(profile) for profile in own)) - others - pinned
    return Contract(
        package=package,
        document=document,
        image_name=name,
        image_path=native / f"{name}{suffix}",
        relay_path=native / f"{relay['value']}{suffix}",
        gateway=profiles[gateway_name],
        worker=profiles[worker_name],
        worker_arguments=tuple(str(argument) for argument in worker_arguments[0]),
        stores_state_arguments=stores["stores-state"],
        setup_arguments=stores["setup"],
        agent_only_names=frozenset(agent_only),
    )


@dataclass
class Running:
    """One program the probe started: its pipes, the end of its standard error, and its whole tree."""

    process: asyncio.subprocess.Process
    _standard_error: bytearray = field(default_factory=bytearray)
    _drain: asyncio.Task[None] | None = None

    @classmethod
    async def start(cls, command: Sequence[str], environment: Mapping[str, str], *, stdin: bytes, cwd: Path) -> Running:
        """Start ``command`` with ``stdin`` written to it, standard output and error piped."""
        options: dict[str, Any] = {} if sys.platform == "win32" else {"start_new_session": True}
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=dict(environment),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **options,
        )
        running = cls(process)
        running._drain = asyncio.create_task(running._drain_standard_error())
        if process.stdin is not None:
            with contextlib.suppress(OSError):
                process.stdin.write(stdin)
                await process.stdin.drain()
        return running

    async def _drain_standard_error(self) -> None:
        stream = self.process.stderr
        while stream is not None and (chunk := await stream.read(4096)):
            self._standard_error += chunk
            del self._standard_error[:-_STANDARD_ERROR_BYTES]

    async def first_line(self, timeout: float) -> bytes | None:
        """Return the first standard-output line, ``b""`` once the output ends, or ``None`` past the bound."""
        stream = self.process.stdout
        if stream is None:
            return b""
        try:
            return await asyncio.wait_for(stream.readline(), timeout)
        except TimeoutError:
            return None

    @property
    def pid(self) -> int:
        """The program's process identifier."""
        return self.process.pid

    async def end(self, grace: float = STOP_SECONDS) -> int | None:
        """Close standard input, wait ``grace`` seconds, kill the tree if it still runs; return the exit status."""
        if self.process.stdin is not None:
            with contextlib.suppress(OSError):
                self.process.stdin.close()
        try:
            await asyncio.wait_for(self.process.wait(), grace)
        except TimeoutError:
            await self.kill()
        if self._drain is not None:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._drain, 5.0)
        return self.process.returncode

    async def kill(self) -> None:
        """Kill the program and everything it started."""
        if self.process.returncode is None:
            if sys.platform == "win32":
                taskkill = shutil.which("taskkill")
                if taskkill is not None:
                    killer = await asyncio.create_subprocess_exec(
                        taskkill,
                        "/F",
                        "/T",
                        "/PID",
                        str(self.process.pid),
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await killer.wait()
            else:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(self.process.pid, signal.SIGKILL)
            with contextlib.suppress(ProcessLookupError):
                self.process.kill()
        await self.process.wait()

    def standard_error(self) -> bytes:
        """The end of what the program wrote to standard error."""
        return bytes(self._standard_error)


async def run_to_end(
    command: Sequence[str], environment: Mapping[str, str], *, cwd: Path, timeout: float
) -> tuple[int, bytes, bytes]:
    """Run ``command`` to its end within ``timeout`` seconds, killing its tree past it."""
    running = await Running.start(command, environment, stdin=b"", cwd=cwd)
    stdout = running.process.stdout
    collected = b""
    try:
        if stdout is not None:
            collected = await asyncio.wait_for(stdout.read(), timeout)
    except TimeoutError:
        await running.kill()
        raise ProbeFailedError(f"{command[0]} did not end within {timeout:g} s and was killed") from None
    status = await running.end(timeout)
    return (-1 if status is None else status), collected, running.standard_error()


def _folded(contract: Contract, name: str) -> str:
    return name.upper() if contract.windows else name


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.realpath(left)) == os.path.normcase(os.path.realpath(right))


def declared_path(contract: Contract, environment: Mapping[str, str]) -> list[str]:
    """Compose a ``PATH`` the way the package declares: its directories, then the system's."""
    declared = contract.section["path"]
    entries: list[str] = []
    for entry in declared["entries"]:
        if entry["kind"] == "package":
            entries.append(str(contract.package if entry["value"] in {"", "."} else contract.package / entry["value"]))
        elif entry["kind"] == "external":
            entries.extend(part for part in environment.get(entry["value"], "").split(os.pathsep) if part)
        elif contract.windows:
            system = {_folded(contract, name): value for name, value in environment.items()}
            base = system[_folded(contract, declared["windows_system"]["variable"])]
            entries.append(str(Path(base, *declared["windows_system"]["subpaths"])))
        else:
            entries.extend(declared["posix_system"])
    return entries


def classify_gateway(line: bytes | None, status: int | None, standard_error: bytes) -> str:
    """Read the gateway's first protocol line: ``unproven`` or ``ready``; anything else raises why not."""
    if line is None:
        raise ProbeFailedError("the gateway wrote no protocol line before the timeout")
    if not line.strip():
        refusal = native_launch_refusal_from(standard_error)
        if refusal.code is not None:
            raise ProbeFailedError(
                f"the host refused the gateway launch before Python started: {refusal.code.value} ({refusal.subject})"
            )
        tail = standard_error.decode("utf-8", "replace").strip().splitlines()[-1:]
        raise ProbeFailedError(f"the gateway ended with status {status} and wrote no protocol line; stderr ends {tail}")
    try:
        message = json.loads(line)
    except ValueError:
        raise ProbeFailedError(f"the gateway's first line is not JSON: {line[:120]!r}") from None
    event = message.get("event") if isinstance(message, dict) else None
    if event == "agent_ready":
        return "ready"
    if event == "refused":
        code = str(message.get("code"))
        if code == _UNPROVEN:
            return "unproven"
        if code in _SETUP_ADVICE:
            raise SetupError(f"the gateway refused with {code}: {_SETUP_ADVICE[code]}")
        raise ProbeFailedError(f"the gateway refused with {code}, which is not {_UNPROVEN}")
    raise ProbeFailedError(f"the gateway's first line is neither agent_ready nor a refusal: {line[:120]!r}")


def check_worker_reexecution(
    children: Sequence[tuple[str, tuple[str, ...]]], image: Path, worker_arguments: Sequence[str]
) -> None:
    """Hold a ready gateway's children to the image keeping itself as ``sys.executable`` and never frozen."""
    if not any(
        _same_path(program, str(image)) and arguments == tuple(worker_arguments) for program, arguments in children
    ):
        raise ProbeFailedError(
            f"no process the gateway started is the agent image run as {list(worker_arguments)}: "
            f"the image is not its own sys.executable, or sys.frozen is set; children seen: {children}"
        )


@dataclass(frozen=True)
class Result:
    """The outcome of one check: what it showed, and what it could not yet show."""

    name: str
    detail: str = ""
    failure: str | None = None
    pending: tuple[str, ...] = ()


class Probe:
    """The checks, run against one package with one launcher inside a directory the probe owns."""

    def __init__(
        self,
        contract: Contract,
        names: AgentNames,
        launcher: Launcher,
        work: Path,
        *,
        timeout: float = FIRST_LINE_SECONDS,
        worker_wait: float = WORKER_WAIT_SECONDS,
    ) -> None:
        """Hold the declaration, the agent's names and the directories every check shares."""
        self.contract, self.names, self.launcher, self.timeout = contract, names, launcher, timeout
        self.worker_wait = worker_wait
        self.hosted, self.storage = work / "hosted", work / "storage"
        self._stores: Result | ProbeFailedError | None = None
        self.hosted.mkdir()
        self.storage.mkdir()

    def _composed(self) -> dict[str, str]:
        """The gateway's environment as the runtime composes it for this root."""
        return agent_launch_environment(
            storage_root=self.storage, agent_root=self.hosted, relay=self.contract.relay_path, received=os.environ
        )

    async def undeclared_invocation(self) -> Result:
        """An invocation the agent image does not declare ends the launch with the refusal line and no Python."""
        declared = self.contract.section["native_host"]
        expected_status, code = declared["launch_profile_refused"], NativeLaunchRefusalCode.INVOCATION_UNDECLARED.value
        if code not in declared["refusals"]:
            raise SetupError(f"the package declares no {code} refusal: {declared['refusals']}")
        command = self.launcher.image(self.contract.image_path, _UNDECLARED_ARGUMENTS)
        status, standard_output, standard_error = await run_to_end(
            command, os.environ, cwd=self.hosted, timeout=self.timeout
        )
        line = json.dumps({"native_refusal": code, "subject": self.contract.image_name}, separators=(",", ":"))
        if status != expected_status:
            raise ProbeFailedError(f"the image exited {status}, not {expected_status}")
        if standard_error.decode("utf-8", "replace").strip() != line or standard_output:
            raise ProbeFailedError(
                f"the host wrote {standard_error!r} to standard error and {standard_output!r} to standard "
                f"output; expected exactly {line} on standard error"
            )
        return Result("undeclared invocation", f"exit {status}, {line}")

    async def _store_step(self, arguments: Sequence[str]) -> tuple[int, dict[str, Any]]:
        """Run one of the image's own store invocations in the gateway's environment; return its status and answer."""
        status, standard_output, standard_error = await run_to_end(
            self.launcher.image(self.contract.image_path, arguments),
            self._composed(),
            cwd=self.hosted,
            timeout=self.timeout,
        )
        refusal = native_launch_refusal_from(standard_error) if status != 0 else None
        if refusal is not None and refusal.code is not None:
            raise ProbeFailedError(
                f"the host refused the {arguments[-1]} launch before Python started: "
                f"{refusal.code.value} ({refusal.subject})"
            )
        try:
            answer = json.loads(standard_output)
        except ValueError:
            answer = None
        return status, answer if isinstance(answer, dict) else {}

    async def _stores_state(self) -> str:
        """Ask the image for the synthetic hosted root's stores state; it must answer with one of the four states."""
        status, answer = await self._store_step(self.contract.stores_state_arguments)
        state = answer.get("state")
        if status != 0 or state not in _STORES_STATES:
            raise ProbeFailedError(f"stores-state did not answer with a state (exit {status}): {sorted(answer)}")
        return str(state)

    async def stores(self) -> Result:
        """The image's own store invocations bring the synthetic hosted root to current, as a host does."""
        if self._stores is None:
            try:
                self._stores = await self._bring_stores_current()
            except ProbeFailedError as failure:
                self._stores = failure
        if isinstance(self._stores, ProbeFailedError):
            raise self._stores
        return self._stores

    async def _bring_stores_current(self) -> Result:
        before = await self._stores_state()
        status, answer = await self._store_step(self.contract.setup_arguments)
        if status != 0 or answer.get("status") not in _SETUP_STATUSES:
            raise ProbeFailedError(f"setup did not succeed (exit {status}): status {answer.get('status')!r}")
        after = await self._stores_state()
        if after != "current":
            raise ProbeFailedError(f"stores-state reads {after!r} after setup; a hosted serve needs current")
        return Result("agent stores", f"stores-state answered {before!r}; setup succeeded; stores-state reads current")

    async def gateway(self) -> Result:
        """A hosted gateway given the runtime's empty frame refuses as unproven, or reports ready, and is stopped."""
        try:
            await self.stores()
        except ProbeFailedError as failure:
            raise SetupError(f"the hosted root's stores could not be made current: {failure}") from failure
        frame = build_credential_frame({})
        running = await Running.start(
            self.launcher.image(self.contract.image_path, GATEWAY_ARGUMENTS),
            self._composed(),
            stdin=bytes(frame),
            cwd=self.hosted,
        )
        try:
            line = await running.first_line(self.timeout)
            status = await running.end(10.0) if line is None or line == b"" else None
            verdict = classify_gateway(line, status, running.standard_error())
            if verdict == "ready":
                await self._worker_reexecuted(running.pid)
                return Result("hosted gateway", "agent_ready; its worker re-executed the agent image")
        finally:
            await running.end()
        return Result(
            "hosted gateway",
            f"refused {_UNPROVEN}: the gateway received its hosted root, ports and relay",
            pending=(
                "agent_ready and the worker re-execution (sys.executable is the image, sys.frozen is unset) need the "
                "agent's recorded hosted-lane proof",
            ),
        )

    async def _worker_reexecuted(self, pid: int) -> None:
        """Wait for a ready gateway's worker to appear as the agent image run with the worker invocation."""
        clock = asyncio.get_running_loop().time
        deadline = clock() + self.worker_wait
        while True:
            try:
                check_worker_reexecution(
                    self.launcher.children(pid), self.contract.image_path, self.contract.worker_arguments
                )
            except ProbeFailedError:
                if clock() > deadline:
                    raise
                await asyncio.sleep(0.5)
            else:
                return

    async def worker(self) -> Result:
        """The worker invocation starts under the image with the gateway's settings and reports the port it bound."""
        token = secrets.token_hex(16)
        environment = {
            **self._composed(),
            self.names.worker_port: "0",
            self.names.gateway_url: "http://127.0.0.1:1",
            self.names.worker_host: "127.0.0.1",
            self.names.gateway_lifetime_id: "launch-probe",
            self.names.worker_generation: "1",
        }
        frame = json.dumps({"version": 1, "credentials": {}, "internal_token": token}).encode("ascii") + b"\n"
        running = await Running.start(
            self.launcher.image(self.contract.image_path, self.contract.worker_arguments),
            environment,
            stdin=frame,
            cwd=self.hosted,
        )
        try:
            line = await running.first_line(self.timeout)
            if line is None or line == b"":
                await running.end(10.0)
            bound = None
            with contextlib.suppress(ValueError, TypeError):
                bound = json.loads(line or b"null")
            if not (
                isinstance(bound, dict) and bound.get("event") == "worker_bound" and isinstance(bound.get("port"), int)
            ):
                refusal = native_launch_refusal_from(running.standard_error())
                reason = (
                    f"the host refused the worker launch: {refusal.code.value} ({refusal.subject})"
                    if refusal.code is not None
                    else f"first line {line!r}, stderr ends {running.standard_error()[-200:]!r}"
                )
                raise ProbeFailedError(f"the worker did not report the port it bound: {reason}")
        finally:
            await running.end(grace=5.0)
        return Result("worker", f"bound port {bound['port']} with its hosted root, host and gateway settings")

    async def python_image(self) -> Result:
        """The generic interpreter clears agent-only names, composes the declared PATH and pins the default root."""
        contract = self.contract
        defaults = [rule for rule in contract.document["root"]["installed_defaults"] if rule["platform"] == _platform()]
        base_variable = defaults[0]["candidates"][0]["variable"]
        data = self.hosted.parent / "data"
        data.mkdir()
        root_variable = _folded(contract, contract.document["root"]["variable"])
        environment = {name: value for name, value in os.environ.items() if _folded(contract, name) != root_variable}
        environment.update(dict.fromkeys(contract.agent_only_names, "launch-probe-sentinel"))
        environment[base_variable] = str(data)
        status, standard_output, standard_error = await run_to_end(
            self.launcher.python(["-c", _REPORT_PROGRAM]), environment, cwd=self.hosted, timeout=self.timeout
        )
        if status != 0:
            raise ProbeFailedError(
                f"the interpreter could not report its environment (exit {status}): {standard_error[-300:]!r}"
            )
        report = json.loads(standard_output)
        defined = {_folded(contract, name): value for name, value in report["environment"].items()}
        survivors = sorted(name for name in contract.agent_only_names if _folded(contract, name) in defined)
        if survivors:
            raise ProbeFailedError(f"the generic interpreter image let agent-only names through: {survivors}")
        root = defined.get(_folded(contract, contract.document["root"]["variable"]))
        if root is None or not _same_path(root, report["default"]):
            raise ProbeFailedError(
                f"the interpreter's pinned root {root!r} is not the command line's default {report['default']!r}"
            )
        expected = declared_path(contract, environment)
        actual = defined.get("PATH", "").split(os.pathsep)
        if len(actual) != len(expected) or not all(_same_path(a, e) for a, e in zip(actual, expected, strict=True)):
            raise ProbeFailedError(f"the interpreter's PATH {actual} is not the declared composition {expected}")
        return Result(
            "generic interpreter",
            f"cleared {len(contract.agent_only_names)} agent-only names, PATH is the declared composition, "
            "pinned root equals the command line's default",
        )


def _platform() -> str:
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


async def run_probe(
    package: Path,
    document: Mapping[str, Any],
    *,
    launcher: Launcher | None = None,
    names: AgentNames | None = None,
    timeout: float = FIRST_LINE_SECONDS,
) -> list[Result]:
    """Run every check and return one result each; a failing check does not stop the others."""
    contract = read_contract(package, document)
    resolved = installed_agent_names() if names is None else names
    with tempfile.TemporaryDirectory(prefix="cadrumo-launch-probe-", ignore_cleanup_errors=True) as directory:
        probe = Probe(contract, resolved, launcher or Launcher(), Path(directory), timeout=timeout)
        results: list[Result] = []
        checks = (
            ("undeclared invocation", probe.undeclared_invocation),
            ("agent stores", probe.stores),
            ("hosted gateway", probe.gateway),
            ("worker", probe.worker),
            ("generic interpreter", probe.python_image),
        )
        for name, check in checks:
            try:
                results.append(await check())
            except ProbeFailedError as failure:
                prefix = "set-up error: " if isinstance(failure, SetupError) else ""
                results.append(Result(name, failure=prefix + str(failure)))
        return results


def main(arguments: Sequence[str], *, launcher: Launcher | None = None, names: AgentNames | None = None) -> int:
    """Probe the package named first with the contract named second; exit 0 when every check holds."""
    package = Path(arguments[0]).resolve(strict=True)
    document = json.loads(Path(arguments[1]).read_text(encoding="utf-8"))
    results = asyncio.run(run_probe(package, document, launcher=launcher, names=names))
    failed = False
    for result in results:
        if result.failure is None:
            sys.stdout.write(f"ok   {result.name}: {result.detail}\n")
        else:
            failed = True
            sys.stdout.write(f"FAIL {result.name}: {result.failure}\n")
        for note in result.pending:
            sys.stdout.write(f"     pending: {note}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
