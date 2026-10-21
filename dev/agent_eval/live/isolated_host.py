"""Stand the copied package up on a fresh storage root and act as the person through its command line.

The orchestrator here only starts processes and reads JSON. Every step that
touches storage is the package's own code: the runtime installation record and
the runtime launch run in :mod:`.package_host` under the copy's interpreter, and
profile creation, sign-in and tax oracle reads use the copy's ``bin/aeat.exe``;
authentication/access management use ``bin/cadrumo-runtime.exe``, and key issuance
uses the package's SDK with a separate runtime approval. Secrets go to the command line only on its
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
import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Protocol

from cadrumo.core.profile_session import KeychainUnavailability
from cadrumo_runtime.adapters.windows_process import WindowsProcessScope
from dev.packaging.command_execution import run_command
from dev.runtime_lifecycle.caller_owned_root import AcceptanceError
from dev.runtime_lifecycle.proof_support import ProcessIdentity, verified_relay
from dev.runtime_lifecycle.session_holder import WindowsRuntimeSessionHolder

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
_NO_INPUT_CHANNEL_CONDITION: Final = "profile.human.input_channel_available"
"""The precondition a profile-bound verb fails when its sign-in cannot be resumed and no terminal can prompt.

The lane always supplies the password channel, so this refusal can only mean the sign-in was never kept.
"""


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
        self._holder: WindowsRuntimeSessionHolder | None = None
        self._attendance_stop: threading.Event | None = None
        self._attendance_thread: threading.Thread | None = None
        self._invocation: ProcessIdentity | None = None

    @property
    def python(self) -> Path:
        """The copy's own interpreter."""
        return self.package / "python.exe"

    @property
    def cli_image(self) -> Path:
        """The copy's command line."""
        return self.package / "bin" / "aeat.exe"

    @property
    def runtime_image(self) -> Path:
        """The copy's runtime authority command image."""
        return self.package / "bin" / "cadrumo-runtime.exe"

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
        return self._command(self.cli_image, arguments, secret=secret, profile_secret=profile_secret, timeout=timeout)

    def runtime_cli(
        self,
        *arguments: str,
        secret: Mapping[str, Any] | None = None,
        profile_secret: str | None = None,
        timeout: float = _CLI_SECONDS,
    ) -> CliResult:
        """Run authentication or access management through the package's runtime image."""
        return self._command(
            self.runtime_image, arguments, secret=secret, profile_secret=profile_secret, timeout=timeout
        )

    def _command(
        self,
        image: Path,
        arguments: Sequence[str],
        *,
        secret: Mapping[str, Any] | None,
        profile_secret: str | None,
        timeout: float,
    ) -> CliResult:
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
        environment = dict(self.environment)
        if image == self.runtime_image:
            environment["CADRUMO_CLI_REVEAL_IDENTIFIERS"] = "true"
        completed = run_command(
            [str(image), *root_options, *tail],
            cwd=self.root,
            environment=environment,
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

    def request_key(self, person: Person, categories: Sequence[str]) -> CliResult:
        """Receive only the reference of a runtime-approved key from the packaged requester."""
        request_out = self.run.control / "key-request.json"
        request_out.unlink(missing_ok=True)
        (delivered,) = self.package_python(
            "request-key",
            "--profile-id",
            person.profile_id,
            "--request-out",
            str(request_out),
            *(argument for category in categories for argument in ("--category", category)),
        )
        if delivered.get("event") != "key_delivered" or not isinstance(delivered.get("result"), dict):
            raise RuntimeError("the packaged requester returned no protected delivery receipt")
        return CliResult(
            arguments=("request-key",), returncode=0, document={"status": "success", "result": delivered["result"]}
        )

    def requested_key(self, person: Person) -> dict[str, Any] | None:
        """Observe the actual requester's nonsecret review identity before approval."""
        path = self.run.control / "key-request.json"
        if not path.exists():
            return None
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("profile_id") != person.profile_id:
            raise RuntimeError("the prepared SDK request belongs to another profile")
        receipt = document.get("receipt")
        if not isinstance(receipt, dict) or not isinstance(receipt.get("request_id"), str):
            raise RuntimeError("the actual SDK requester omitted its safe review identity")
        return receipt

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

    def sign_in(self, person: Person, *, require_native_custody: bool = False) -> CliResult:
        """Hold the person's explicit proof; key scenarios separately require native custody."""
        result: CliResult | None = None
        if require_native_custody:
            result = self.cli("config", "login", secret={"passphrase": person.password})
            classify_sign_in(result)
        self._stop_attendance()
        holder = WindowsRuntimeSessionHolder(
            self.runtime_image,
            profile_id=uuid.UUID(person.profile_id),
            environment=self.environment,
            password=bytearray(person.password, "utf-8"),
        )
        self._holder = holder
        self._resources.callback(holder.close)
        observed = holder.command("status")
        status = observed.get("status")
        if (
            observed.get("kind") != "profile_status"
            or not isinstance(status, dict)
            or status.get("session_id") != holder.identity["session_id"]
            or status.get("profile_id") != person.profile_id
            or status.get("credential_authenticated") is not True
            or status.get("denial") is not None
        ):
            self._stop_attendance()
            raise RuntimeError("the exact person's held session is not authoritative")
        if result is None:
            result = CliResult(
                arguments=("session", "hold"),
                returncode=0,
                document={
                    "status": "success",
                    "result": {**observed, "idle_deadline": status["session_expires_at"], "session_persisted": False},
                },
            )
        stop = threading.Event()
        self._attendance_stop = stop

        def attend() -> None:
            while not stop.is_set():
                try:
                    inventory = holder.command("attendance_inventory")
                    if inventory.get("kind") != "attendance_inventory":
                        return
                    candidates = inventory.get("candidates")
                    if not isinstance(candidates, list):
                        return
                    for candidate in candidates:
                        if not isinstance(candidate, dict) or not isinstance(candidate.get("attendance_id"), str):
                            return
                        approved = self._owned_relay(candidate.get("process_id"))
                        decision = holder.command(
                            "attendance_decision", attendance_id=candidate["attendance_id"], approve=approved
                        )
                        if decision.get("kind") != "attendance_decided" or decision.get("approved") is not approved:
                            return
                except (AcceptanceError, OSError, ValueError):
                    return
                stop.wait(0.25)

        self._attendance_thread = threading.Thread(target=attend, name="live-person-attendance", daemon=True)
        self._attendance_thread.start()
        self._resources.callback(self._stop_attendance)
        return result

    def retain_invocation(self, process_id: int) -> None:
        """Capture the kernel incarnation supplied by the actual subprocess launch."""
        self._invocation = ProcessIdentity.capture(process_id)

    def _owned_relay(self, process_id: object) -> bool:
        """Admit only a packaged relay under the current retained invocation."""
        return verified_relay(process_id, self.mcp_image, self._invocation)

    def _stop_attendance(self) -> None:
        if self._attendance_stop is not None:
            self._attendance_stop.set()
        if self._attendance_thread is not None:
            self._attendance_thread.join(timeout=35)
            if self._attendance_thread.is_alive():
                raise RuntimeError("the person's attendance observer did not settle")
        self._attendance_stop, self._attendance_thread = None, None
        if self._holder is not None:
            self._holder.close()
            self._holder = None

    def sign_out(self) -> CliResult:
        """Sign the person out and release their exact held-session observer."""
        result = self.cli("config", "logout")
        self._stop_attendance()
        return result

    def release_held_session(self) -> None:
        """Release the original holder after explicit lock or observed expiry."""
        self._stop_attendance()

    def delete_stored_sign_in(self, person: Person) -> None:
        """Remove the profile's stored sign-in, both halves, through the package's own code."""
        self.package_python("delete-session", "--root", str(self.root), "--profile-id", person.profile_id)


def _keychain_reasons(document: Mapping[str, Any]) -> tuple[str, ...]:
    """The typed keychain reasons the product attached to the refusal or to its notices."""
    known = {reason.value for reason in KeychainUnavailability}
    contexts: list[object] = []
    error = document.get("error")
    if isinstance(error, dict):
        contexts.append(error.get("context"))
    notices = document.get("notices")
    if isinstance(notices, list):
        contexts.extend(notice.get("context") for notice in notices if isinstance(notice, dict))
    reasons: list[str] = []
    for context in contexts:
        reason = context.get("keychain") if isinstance(context, dict) else None
        if isinstance(reason, str) and reason in known:
            reasons.append(reason)
    return tuple(reasons)


def _refused_for_want_of_a_kept_sign_in(document: Mapping[str, Any]) -> bool:
    """True for the CLI-boundary refusal whose typed action names the absent password channel."""
    error = document.get("error")
    if not isinstance(error, dict) or error.get("code") != "REFUSED_CLI_BOUNDARY":
        return False
    action = error.get("action")
    return isinstance(action, dict) and bool(action.get("failed_condition_id") == _NO_INPUT_CHANNEL_CONDITION)


def classify_sign_in(result: CliResult) -> None:
    """Turn a sign-in the credential store could not keep into ``unavailable``, never a pass.

    Key scenarios require native credential custody. A logon session the store
    refuses (an SSH logon on Windows answers WinError 1312) cannot run them.
    No-key connections use attendance under the separately held human session.
    """
    tokens = result.error_tokens
    keychain = _keychain_reasons(result.document)
    if (
        any(signal in token for token in tokens for signal in _KEYRING_SIGNALS)
        or keychain
        or _refused_for_want_of_a_kept_sign_in(result.document)
    ):
        shown = [*tokens, *(f"keychain:{reason}" for reason in keychain)]
        raise UnavailableError(
            CREDENTIAL_STORE_UNAVAILABLE,
            f"the OS credential store refused this logon session ({'/'.join(shown) or 'sign-in not resumable'}); "
            "stored sign-in and API keys need an interactive logon",
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


class McpImageHost(Protocol):
    """What launching the packaged MCP server needs of the hosted package."""

    @property
    def mcp_image(self) -> Path:
        """The packaged MCP server's executable."""
        ...

    @property
    def environment(self) -> Mapping[str, str]:
        """The allow-listed environment the server runs in."""
        ...


def mcp_launch(
    host: McpImageHost, *, profile_id: str | None = None, credential_reference: str | None = None
) -> tuple[str, Sequence[str], dict[str, str]]:
    """The packaged MCP server's command, arguments and allow-listed environment.

    With a key, the server is told the profile and the reference the person
    configured; the key itself never appears. Without one it asks the exact
    held person session for approval through runtime attendance.
    """
    arguments: list[str] = []
    if credential_reference is not None:
        if profile_id is None:
            raise ValueError("a credential reference belongs to one profile")
        arguments = ["--profile-id", profile_id, "--credential-reference", credential_reference]
    return str(host.mcp_image), tuple(arguments), dict(host.environment)
