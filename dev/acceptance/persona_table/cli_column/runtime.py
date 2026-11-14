"""The tree under test as an installed product: its venv, a disposable root, a caller-owned runtime, and teardown.

The CLI column runs the ``aeat`` command line of an installed wheel built from a snapshot of the tree, against a
``cadrumo-runtime --configured-root`` that this process owns. Nothing here reads or writes the installed default root
or the operator's profile: the root is a fresh ``cadrumo-e2e-*`` directory in the account's temporary folder, outside
every Git project, and the product environment of every child is rebuilt from an allowlist.

The profile passphrase is the synthetic one of the persona world. It reaches a child only on its standard input,
once per command. Before the runtime is drained the served profile is signed out through the person's own
``config logout`` command, so a sign-in a command made leaves nothing in the account's credential store. The
publisher's Google OAuth client reaches the wheel build alone, as a variable of that one process.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from cadrumo.tests.env_scope import scoped_env_var
from cadrumo_runtime.application.development_root import mark_development_root
from dev.acceptance.installed_cli import InstalledCli, InstalledCliError, build_installed_cli_environment
from dev.desktop_agent_live.disposable_root import create_root, is_link, remove_root, temporary_parent
from dev.packaging.acquire_common import venv_executable
from dev.packaging.authority_staging import AUTHORITY_ROOT_ENV, stage_published_authority
from dev.packaging.command_execution import CommandResult, run_command
from dev.packaging.google_oauth import build_client_json
from dev.packaging.installed_runtime import installed_cli_runtime

from .hygiene import OAUTH_CLIENT_ENV, Redactor
from .intake import TIMEOUT_STATUS, Kind, Outcome, classify
from .world_report import ReportError, WorldReport, parse_report

BUILD_SECONDS = 3600
WORLD_SECONDS = 1800
_BUILD_SNIPPET = (
    "from dev.packaging.release_cohort_support import client_venv_template\nprint(client_venv_template())\n"
)
_KEPT_PREFIXES = ("CADRUMO_", "AEAT_")
_INTERPRETER_NAMES = frozenset({"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"})
_TAIL_LINES = 12
SIGN_OUT_COMMAND = ("config", "logout")
"""The person's sign-out command, ``aeat config logout NAME``, which proves the person with the passphrase on stdin."""
SIGN_OUT_FAILED_CODE = "acceptance.cli_column.sign_out_failed"


class RuntimeSetupError(RuntimeError):
    """The tree venv, the world or the runtime could not be made ready; the message holds no secret."""


def child_environment(base: Mapping[str, str], *, python_path: Sequence[Path] = ()) -> dict[str, str]:
    """``base`` without any product setting, interpreter selection or OAuth client, plus ``python_path``.

    This is the environment of every child but the build: none of them may see the OAuth client, and a product
    setting is stated explicitly by the child that needs one.
    """
    environment = {
        name: value
        for name, value in base.items()
        if not name.upper().startswith(_KEPT_PREFIXES) and name.upper() not in _INTERPRETER_NAMES
    }
    if python_path:
        environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in python_path)
    return environment


def snapshot_path(snapshot: Path) -> list[Path]:
    """The import roots of a snapshot: its ``src`` and its root."""
    return [snapshot / "src", snapshot]


def e2e_parent(environ: Mapping[str, str] | None = None) -> Path:
    r"""The account's temporary folder, ``%LOCALAPPDATA%\Temp``, where disposable roots live."""
    return temporary_parent(os.environ if environ is None else environ)


def create_e2e_root(parent: Path) -> Path:
    """A fresh ``cadrumo-e2e-*`` root directly below ``parent``, outside every Git project."""
    return create_root(parent)


def teardown_root(root: Path, parent: Path) -> list[str]:
    """Remove the disposable root without following any link; name each path left behind.

    The root is verified before anything is removed: it must be named like a disposable root, be a real directory and
    not a link, and resolve to a direct child of ``parent``. Anything else is refused with an ``AcceptanceError``.
    """
    return remove_root(root, parent)


def remove_snapshot(snapshot: Path) -> list[str]:
    """Remove a snapshot the run built from, which holds the build's OAuth client; name each path left behind.

    Only a real directory named ``snap-*`` that is no link and holds no ``.git`` entry is removed.
    """
    if not snapshot.name.startswith("snap-") or is_link(snapshot) or not snapshot.is_dir():
        raise RuntimeSetupError(f"refusing to remove {snapshot}: not a snapshot directory")
    if (snapshot / ".git").exists():
        raise RuntimeSetupError(f"refusing to remove {snapshot}: it holds a .git entry")
    left: list[str] = []

    def forget(function: object, path: str, error: BaseException) -> None:
        del function
        try:
            Path(path).chmod(stat.S_IWRITE | stat.S_IREAD)
            Path(path).unlink()
        except OSError:
            left.append(f"{path}: {error}")

    shutil.rmtree(snapshot, onexc=forget)
    return left


def _run(command: Sequence[str], cwd: Path, environment: Mapping[str, str], seconds: float) -> CommandResult:
    """Run ``command`` with exactly ``environment``; a command that outlives ``seconds`` is killed with its tree."""
    try:
        return run_command(command, cwd=cwd, environment=environment, timeout_seconds=seconds, errors="replace")
    except subprocess.TimeoutExpired:
        raise RuntimeSetupError(f"a child did not finish within {seconds:.0f} seconds") from None


def _tail(text: str) -> str:
    return "\n".join(text.strip().splitlines()[-_TAIL_LINES:])


def build_environment(snapshot: Path, client: str, base: Mapping[str, str]) -> dict[str, str]:
    """The environment of the wheel build: the allowlist, the snapshot's import roots and the OAuth client."""
    environment = child_environment(base, python_path=snapshot_path(snapshot))
    environment[OAUTH_CLIENT_ENV] = client
    return environment


def build_tree_venv(snapshot: Path, authority: Path, client_root: Path | None, redactor: Redactor, log: Path) -> Path:
    """Build the four-wheel cohort from ``snapshot`` and install it into a private venv; return the venv.

    The published authority is copied into the snapshot first, since the build stages it from there. The OAuth
    client is read from the process environment or ``client_root``'s ``env/.env`` and is set in the environment of
    the build process only. Its output is redacted before it is kept.
    """
    with scoped_env_var(AUTHORITY_ROOT_ENV, str(authority)):
        stage_published_authority(snapshot, snapshot)
    try:
        client = build_client_json(client_root if client_root is not None else snapshot).get_secret_value()
    except ValueError as error:
        raise RuntimeSetupError(f"no Google OAuth client for the build: {redactor.text(str(error))}") from None
    environment = build_environment(snapshot, client, os.environ)
    completed = _run([sys.executable, "-c", _BUILD_SNIPPET], snapshot, environment, BUILD_SECONDS)
    output = redactor.with_client(client).text(f"{completed.stdout}\n{completed.stderr}")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(output, encoding="utf-8", newline="\n")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if completed.returncode != 0 or not lines:
        raise RuntimeSetupError(f"the tree venv was not built (exit {completed.returncode}): {_tail(output)}")
    venv = Path(lines[-1].strip())
    if not venv_executable(venv, "aeat").is_file():
        raise RuntimeSetupError("the tree venv holds no aeat launcher")
    return venv


def run_world(
    snapshot: Path,
    authority: Path,
    storage_root: Path,
    persona: str,
    horizon: int,
    filters: tuple[Sequence[str], Sequence[int]],
    redactor: Redactor,
) -> WorldReport:
    """Materialise the persona's world into ``storage_root`` in an interpreter of its own and read its report."""
    modelos, years = filters
    environment = child_environment(os.environ, python_path=snapshot_path(snapshot))
    environment[AUTHORITY_ROOT_ENV] = str(authority)
    arguments = ["--persona", persona, "--horizon", str(horizon), "--storage-root", str(storage_root)]
    arguments += [item for modelo in modelos for item in ("--modelo", modelo)]
    arguments += [item for year in years for item in ("--year", str(year))]
    command = [sys.executable, "-m", "dev.acceptance.persona_table.cli_column.world", *arguments]
    completed = _run(command, snapshot, environment, WORLD_SECONDS)
    if completed.returncode != 0:
        raise RuntimeSetupError(
            f"the world was not materialised (exit {completed.returncode}): {redactor.text(_tail(completed.stderr))}"
        )
    try:
        return parse_report(completed.stdout)
    except ReportError as error:
        raise RuntimeSetupError(redactor.text(str(error))) from error


@dataclass(frozen=True, slots=True)
class SignOut:
    """One sign-out the runner made at teardown: the profile it addressed and how the command ended."""

    profile: str | None
    outcome: Outcome

    @property
    def finding(self) -> str | None:
        """The typed finding of a sign-out that did not succeed, ``None`` when it did."""
        if self.outcome.kind is Kind.OK:
            return None
        code = self.outcome.code or self.outcome.kind.value
        return (
            f"sign-out at teardown: {' '.join(SIGN_OUT_COMMAND)} {self.profile or '(selected profile)'} ended "
            f"{self.outcome.kind.value} ({code}): a profile-session credential may remain in the account's store"
        )


def _profile_named(args: Sequence[str]) -> str | None:
    """The profile an ``aeat --profile NAME ...`` command is aimed at, ``None`` when it names none."""
    for index, argument in enumerate(args[:-1]):
        if argument == "--profile":
            return args[index + 1]
    return None


class InstalledCommands(Protocol):
    """The installed CLI a runner drives: its sign-in passphrase and one JSON command per fresh process."""

    passphrase: str

    def run(
        self, args: Sequence[str], *, authenticated: bool, allow_error: bool, stdin_payload: str | None = None
    ) -> dict[str, Any]:
        """Run ``args`` and return the envelope it printed."""
        ...


class CliRunner:
    """Run ``aeat`` commands of the tree venv against the served root, one fresh process each.

    A command that does not answer in time is reported with the ``timeout`` status, which the intake maps to an
    unsettled effect; it is never run again. Every profile a passphrase-bearing command was aimed at is remembered,
    and :meth:`sign_out_all` signs each of them out through the person's own sign-out command.
    """

    def __init__(self, cli: InstalledCommands) -> None:
        """Bind the runner to an installed CLI whose passphrase goes on each command's standard input."""
        self._cli = cli
        self._signed_in: dict[str | None, None] = {}
        self.sign_outs: list[SignOut] = []
        """Each sign-out :meth:`sign_out_all` made, in order."""

    def __call__(self, args: Sequence[str], *, authenticated: bool = True) -> Mapping[str, object] | None:
        """Run ``args``; the envelope it printed, a timeout marker, or an adapter error document."""
        if authenticated:
            self._signed_in[_profile_named(args)] = None
        try:
            return self._cli.run(args, authenticated=authenticated, allow_error=True)
        except subprocess.TimeoutExpired:
            return {"status": TIMEOUT_STATUS}

    def sign_out_all(self) -> list[SignOut]:
        """Sign out every profile a command carried the passphrase for; a sign-out that fails is a finding, not a raise.

        The command is ``aeat config logout NAME`` with the passphrase as its machine secret, the way a person ends a
        sign-in from another process. Its outcome, success or not, is kept in :attr:`sign_outs`; nothing is retried.
        """
        made: list[SignOut] = []
        for profile in tuple(self._signed_in):
            made.append(SignOut(profile, self._sign_out(profile)))
            del self._signed_in[profile]
        self.sign_outs.extend(made)
        return made

    def _sign_out(self, profile: str | None) -> Outcome:
        arguments = (*SIGN_OUT_COMMAND, *(() if profile is None else (profile,)), "--secrets-stdin")
        payload = json.dumps({"passphrase": self._cli.passphrase}, separators=(",", ":"))
        try:
            document = self._cli.run(arguments, authenticated=False, allow_error=True, stdin_payload=payload)
        except subprocess.TimeoutExpired:
            return classify({"status": TIMEOUT_STATUS})
        except (OSError, subprocess.SubprocessError, InstalledCliError) as error:
            return Outcome(Kind.ERROR, SIGN_OUT_FAILED_CODE, type(error).__name__)
        return classify(document)


@contextmanager
def signing_out(runner: CliRunner) -> Generator[CliRunner]:
    """Yield ``runner`` and, however the body ends, sign out every profile it signed in before returning.

    The sign-out needs the runtime that served the profile, so this context is entered inside the runtime's own and
    leaves first.
    """
    try:
        yield runner
    finally:
        runner.sign_out_all()


@contextmanager
def served_root(
    template: Path, storage_root: Path, authority: Path, passphrase: str, log: Path
) -> Generator[CliRunner]:
    """Serve ``storage_root`` through the venv's caller-owned runtime and yield a runner of its ``aeat``.

    The root is marked as a development root first; the runtime refuses the installed default root. On exit the
    profiles the runner signed in are signed out first, while the runtime still serves them, then the runtime's
    standard input is closed and its drain (exit 64) is required.
    """
    mark_development_root(storage_root)
    cli = venv_executable(template, "aeat")
    environment = build_installed_cli_environment(storage_root=storage_root, authority_root=authority)
    with installed_cli_runtime(cli, environment, log):
        installed = InstalledCli(cli, storage_root=storage_root, authority_root=authority, passphrase=passphrase)
        with signing_out(CliRunner(installed)) as runner:
            yield runner
