"""Stand the copied package up on a fresh storage root and act as the person through its command line.

The orchestrator here only starts processes and reads JSON. Every step that
touches storage is the package's own code: the runtime installation record and
the runtime launch run in :mod:`.package_host` under the copy's interpreter, and
profile creation, sign-in, key issuance, locks and every oracle read run
through the copy's ``bin/aeat.exe``. Secrets go to the command line only on its
protected stdin channel, held in memory for the run and never written down.

Every packaged process starts from an allow-listed environment. Nothing the
host carries outside the list (a model credential, a messaging token, the
operator's own Cadrumo variables) reaches the runtime, the CLI or the MCP server.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import time
import uuid
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from dev.packaging.command_execution import run_command

from .capture import Scrubber
from .outcome import UnavailableError
from .package_host import READY_FILE, STOP_FILE, STOPPED_FILE

_HOST_SCRIPT: Final = Path(__file__).with_name("package_host.py")
_READY_SECONDS: Final = 180.0
_CLI_SECONDS: Final = 300.0

HOST_ENVIRONMENT_ALLOWLIST: Final = frozenset(
    {
        "ALLUSERSPROFILE",
        "APPDATA",
        "COMMONPROGRAMFILES",
        "COMSPEC",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "NUMBER_OF_PROCESSORS",
        "OS",
        "PATHEXT",
        "PROCESSOR_ARCHITECTURE",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMW6432",
        "PUBLIC",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "USERDOMAIN",
        "USERNAME",
        "USERPROFILE",
        "WINDIR",
    }
)
"""Host variables a packaged process may see. ``PATH`` is rebuilt from the system root, never inherited."""

CREDENTIAL_STORE_UNAVAILABLE: Final = "credential_store_unavailable"
_KEYRING_SIGNALS: Final = ("keyring_unavailable", "KEYRING_UNAVAILABLE", "custody_unavailable", "1312")


def allowlisted_environment(ambient: Mapping[str, str]) -> dict[str, str]:
    """Keep only the allow-listed host variables and rebuild ``PATH`` from the system root."""
    upper = {name.upper(): value for name, value in ambient.items()}
    environment = {name: upper[name] for name in sorted(HOST_ENVIRONMENT_ALLOWLIST) if name in upper}
    system_root = upper.get("SYSTEMROOT", "C:\\Windows")
    environment["PATH"] = os.pathsep.join((f"{system_root}\\System32", system_root, f"{system_root}\\System32\\Wbem"))
    environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
    return environment


def host_values_outside_allowlist(ambient: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """Name and value of every host variable outside the allow-list, for the capture scrubber."""
    return tuple(
        (name, value)
        for name, value in sorted(ambient.items())
        if name.upper() not in HOST_ENVIRONMENT_ALLOWLIST and name.upper() != "PATH" and value
    )


@dataclass(frozen=True, slots=True)
class RunDirectory:
    """One run's directory: the fresh storage root and, beside it, the host's control files."""

    path: Path

    @property
    def root(self) -> Path:
        """The storage root the packaged runtime and command line use."""
        return self.path / "storage"

    @property
    def control(self) -> Path:
        """Where the package host publishes readiness and reads its stop request."""
        return self.path / "control"


def new_run_directory(base: Path) -> RunDirectory:
    """Create one fresh run directory with an empty storage root."""
    run = RunDirectory((base / f"run-{uuid.uuid4().hex[:12]}").resolve())
    run.root.mkdir(parents=True)
    run.control.mkdir()
    return run


def remove_run_directory(run: RunDirectory, base: Path) -> None:
    """Remove a run's directory, refusing anything that is not a run directory under the run base."""
    resolved = run.path.resolve()
    if resolved.parent != base.resolve() or not resolved.name.startswith("run-"):
        raise ValueError(f"refusing to remove {resolved}: not a run directory under {base}")
    shutil.rmtree(resolved, ignore_errors=True)


@dataclass(frozen=True, slots=True)
class CliResult:
    """One packaged command-line invocation's exit status and decoded envelope."""

    arguments: tuple[str, ...]
    returncode: int
    document: dict[str, Any]
    stream: str = "stdout"
    """Which stream carried the envelope: ``stdout``, ``stderr`` or ``none`` when neither decoded."""
    stdout_head: str = ""
    stderr_head: str = ""

    @property
    def ok(self) -> bool:
        """True for a zero exit with a success or warning envelope."""
        return self.returncode == 0 and self.document.get("status") in {"success", "warning"}

    @property
    def result(self) -> dict[str, Any]:
        """The envelope's result object, or an empty one."""
        value = self.document.get("result")
        return value if isinstance(value, dict) else {}

    @property
    def error_tokens(self) -> tuple[str, ...]:
        """The refusal's code and reason tokens, the only refusal text a receipt keeps."""
        error = self.document.get("error")
        if not isinstance(error, dict):
            return ()
        context = error.get("context") if isinstance(error.get("context"), dict) else {}
        values = (error.get("code"), context.get("reason"), context.get("sign_in_reason"))
        return tuple(value for value in values if isinstance(value, str))


@dataclass(slots=True)
class Person:
    """The synthetic person the harness plays: their profile and the password only they know."""

    profile_id: str
    password: str = field(repr=False)

    def secret_values(self) -> tuple[str, ...]:
        """Every value the capture scrubber must remove."""
        return (self.password,)


HEAD_CHARACTERS: Final = 2000


@dataclass(frozen=True, slots=True)
class FailedCall:
    """One command-line call that failed: its name, never its arguments, and the heads of its streams."""

    command: str
    returncode: int
    stream: str
    stdout_head: str
    stderr_head: str


def command_name(arguments: Sequence[str]) -> str:
    """The leading subcommand words of a call: at most three plain words, stopping at an option or a value."""
    words: list[str] = []
    for argument in arguments[:3]:
        if (
            argument.startswith("-")
            or not argument.isascii()
            or not argument.replace("-", "").isalpha()
            or argument != argument.lower()
        ):
            break
        words.append(argument)
    return " ".join(words)


def decode_envelope(stdout: str, stderr: str, returncode: int) -> tuple[dict[str, Any] | None, str]:
    """Decode the JSON envelope from whichever stream carries it, and say which.

    A success writes it to stdout and a refusal historically to stderr, but a
    registered refusal can be written to either, and a process that exits
    early may carry it on the other. The stream the exit status points at is
    tried first. ``(None, "none")`` means neither decodes.
    """
    ordered = (("stdout", stdout), ("stderr", stderr)) if returncode == 0 else (("stderr", stderr), ("stdout", stdout))
    for name, text in ordered:
        candidates = [text.strip(), *[line for line in reversed(text.splitlines()) if line.startswith("{")][:1]]
        for candidate in candidates:
            if not candidate:
                continue
            try:
                document = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(document, dict):
                return document, name
    return None, "none"


def _decoded_events(stdout: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]


class PackageHost:
    """The copied package hosted on one fresh root, until :meth:`close`."""

    def __init__(
        self, package: Path, run: RunDirectory, *, ambient: Mapping[str, str], scrubber: Scrubber | None = None
    ) -> None:
        """Remember the copy and the run directory; nothing starts until :meth:`start`.

        ``scrubber`` cleans the stream heads kept on a call's result and in
        :attr:`failed_calls`; the profile password is added when the person is created.
        """
        self.scrubber = scrubber if scrubber is not None else Scrubber(())
        self.failed_calls: list[FailedCall] = []
        self.package = package
        self.run = run
        self.root = run.root
        self._base_environment = allowlisted_environment(ambient)
        self._base_environment["CADRUMO_AUTHORITY_ROOT"] = str(package / "data" / "authority")
        self._base_environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(run.root)
        self._resources = ExitStack()
        self.environment: dict[str, str] = {}
        self.ready: dict[str, Any] = {}

    @property
    def python(self) -> Path:
        """The copy's own interpreter."""
        return self.package / "python.exe"

    @property
    def cli_image(self) -> Path:
        """The copy's command line."""
        return self.package / "bin" / "aeat.exe"

    @property
    def mcp_image(self) -> Path:
        """The copy's MCP server."""
        return self.package / "bin" / "cadrumo-mcp.exe"

    def package_python(self, *arguments: str, timeout: float = _CLI_SECONDS) -> list[dict[str, Any]]:
        """Run one :mod:`.package_host` subcommand under the copy's interpreter and return its events."""
        completed = run_command(
            [str(self.python), "-I", str(_HOST_SCRIPT), *arguments],
            cwd=self.root,
            environment=self.environment or self._base_environment,
            timeout_seconds=timeout,
            errors="replace",
        )
        events = _decoded_events(completed.stdout)
        if completed.returncode != 0 or not events:
            detail = next((event.get("code", "") for event in events if event.get("event") == "error"), "")
            raise RuntimeError(f"package host {arguments[0]} failed: exit {completed.returncode} {detail}")
        return events

    def start(self) -> None:
        """Start the package host in a kill-on-close job and wait until the packaged runtime answers."""
        scope = WindowsProcessScope()
        self._resources.callback(scope.terminate, timeout=30)
        self._resources.callback(self._request_stop)
        scope.launch(
            executable=self.python,
            arguments=(
                "-I",
                str(_HOST_SCRIPT),
                "serve",
                "--root",
                str(self.root),
                "--package",
                str(self.package),
                "--control",
                str(self.run.control),
            ),
            directory=self.root,
            environment=self._base_environment,
        )
        ready, stopped = self.run.control / READY_FILE, self.run.control / STOPPED_FILE
        deadline = time.monotonic() + _READY_SECONDS
        while not ready.exists():
            if stopped.exists():
                event = json.loads(stopped.read_text(encoding="utf-8"))
                raise RuntimeError(f"the package host stopped before ready: {event.get('event')} {event.get('code')}")
            if time.monotonic() >= deadline:
                raise RuntimeError("the packaged runtime did not report ready in time")
            time.sleep(0.25)
        self.ready = json.loads(ready.read_text(encoding="utf-8"))
        self.environment = dict(self.ready["environment"])

    def _request_stop(self) -> None:
        (self.run.control / STOP_FILE).touch()
        deadline = time.monotonic() + 30
        while not (self.run.control / STOPPED_FILE).exists() and time.monotonic() < deadline:
            time.sleep(0.25)

    def close(self) -> None:
        """Ask the host to stop its runtime, then terminate whatever is left in the job."""
        self._resources.close()

    def cli(
        self,
        *arguments: str,
        secret: Mapping[str, Any] | None = None,
        profile_secret: str | None = None,
        timeout: float = _CLI_SECONDS,
    ) -> CliResult:
        """Run the packaged command line once and decode its JSON envelope.

        ``secret`` goes on ``--secrets-stdin``; ``profile_secret`` is the
        profile password for a profile-bound verb, on ``--profile-secrets-stdin``.
        Neither ever appears in the arguments, the environment or the result.
        """
        if secret is not None and profile_secret is not None:
            raise ValueError("one protected channel per invocation")
        root_options: list[str] = ["--format", "json"]
        payload: dict[str, Any] | None = None
        tail = list(arguments)
        if profile_secret is not None:
            root_options.append("--profile-secrets-stdin")
            payload = {"profile_passphrase": profile_secret}
        elif secret is not None:
            tail.append("--secrets-stdin")
            payload = dict(secret)
        completed = run_command(
            [str(self.cli_image), *root_options, *tail],
            cwd=self.root,
            environment=self.environment,
            timeout_seconds=timeout,
            errors="replace",
            input_text=None if payload is None else json.dumps(payload),
        )
        stdout_head = self.scrubber.scrub(completed.stdout[:HEAD_CHARACTERS])
        stderr_head = self.scrubber.scrub(completed.stderr[:HEAD_CHARACTERS])
        decoded, stream = decode_envelope(completed.stdout, completed.stderr, completed.returncode)
        document = decoded
        if document is None:
            document = {
                "status": "error",
                "error": {
                    "code": "UNDECODABLE_ENVELOPE",
                    "context": {
                        "reason": f"exit_{completed.returncode}",
                        "stdout_head": stdout_head,
                        "stderr_head": stderr_head,
                    },
                },
            }
        result = CliResult(
            arguments=tuple(arguments),
            returncode=completed.returncode,
            document=document,
            stream=stream,
            stdout_head=stdout_head,
            stderr_head=stderr_head,
        )
        if not result.ok:
            self.failed_calls.append(
                FailedCall(command_name(arguments), completed.returncode, stream, stdout_head, stderr_head)
            )
        return result

    def create_person(self, name: str) -> Person:
        """Create a synthetic profile with a random password the agent never sees."""
        password = f"Live-eval-{secrets.token_urlsafe(24)}!"
        created = self.cli(
            "config",
            "profile",
            "create",
            name,
            "--quiet",
            secret={"passphrase": password, "passphrase_confirmation": password},
        )
        if not created.ok:
            raise RuntimeError(f"profile creation refused: {'/'.join(created.error_tokens)}")
        # The packaged command line prints identifiers redacted; the package's own pointer names the profile.
        (selected,) = (event for event in self.package_python("active-profile", "--root", str(self.root)))
        self.scrubber.add("profile_password", password)
        return Person(profile_id=str(selected["profile_id"]), password=password)

    def state_profile(self, person: Person, options: Sequence[str]) -> None:
        """State the profile facts and complete the setup, as the person does at the command line."""
        for arguments in (("config", "profile", "edit", "--quiet", *options), ("config", "profile", "complete-setup")):
            result = self.cli(*arguments, profile_secret=person.password)
            if not result.ok:
                raise RuntimeError(f"{' '.join(arguments[:3])} refused: {'/'.join(result.error_tokens)}")

    def sign_in(self, person: Person) -> CliResult:
        """Sign the person in on the protected channel; a refused credential store is unavailable."""
        result = self.cli("config", "login", secret={"passphrase": person.password})
        classify_sign_in(result)
        return result

    def sign_out(self) -> CliResult:
        """Sign the person out, as they would at a terminal."""
        return self.cli("config", "logout")

    def delete_stored_sign_in(self, person: Person) -> None:
        """Remove the profile's stored sign-in, both halves, through the package's own code."""
        self.package_python("delete-session", "--root", str(self.root), "--profile-id", person.profile_id)


def classify_sign_in(result: CliResult) -> None:
    """Turn a sign-in the credential store could not keep into ``unavailable``, never a pass.

    A stored sign-in is the only door an agent may use besides a key, and both
    need the platform credential store. A logon session the store refuses (an
    SSH logon on Windows answers WinError 1312) cannot run the lane.
    """
    tokens = result.error_tokens
    if any(signal in token for token in tokens for signal in _KEYRING_SIGNALS):
        raise UnavailableError(
            CREDENTIAL_STORE_UNAVAILABLE,
            f"the OS credential store refused this logon session ({'/'.join(tokens)}); stored sign-in and API keys "
            "need an interactive logon",
        )
    if not result.ok:
        raise RuntimeError(f"sign-in refused: {'/'.join(tokens) or result.returncode}")
    if result.result.get("session_persisted") is not True:
        notices = result.document.get("notices")
        codes = (
            [str(notice.get("code")) for notice in notices if isinstance(notice, dict)]
            if isinstance(notices, list)
            else []
        )
        raise UnavailableError(
            CREDENTIAL_STORE_UNAVAILABLE,
            "the sign-in was admitted but the OS credential store did not keep it, so MCP cannot resume it "
            f"({'/'.join(codes) or 'session_persisted=false'}); run on an interactive logon",
        )


def mcp_launch(
    host: PackageHost, *, profile_id: str | None = None, credential_reference: str | None = None
) -> tuple[str, Sequence[str], dict[str, str]]:
    """The packaged MCP server's command, arguments and allow-listed environment.

    With a key, the server is told the profile and the reference the person
    configured; the key itself never appears. Without one it resumes the
    person's sign-in.
    """
    arguments: list[str] = []
    if credential_reference is not None:
        if profile_id is None:
            raise ValueError("a credential reference belongs to one profile")
        arguments = ["--profile-id", profile_id, "--credential-reference", credential_reference]
    return str(host.mcp_image), tuple(arguments), dict(host.environment)
