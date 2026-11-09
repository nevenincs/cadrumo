"""Sign in to a provider by hand from a console, through the bundled agent's own login.

The agent runs against the same isolated provider home the desktop application
uses, so the application finds the sign-in on its next status read. The
operator's terminal is handed to the agent unchanged: nothing is captured,
because the provider's login may print a device code there.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import UUID

from cadrumo.core.storage_environment import configured_storage_root

from ..host.launch_environment import (
    EXTERNAL_BIN_DIRECTORIES_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    agent_binary_directories,
    system_environment,
)
from .agent_programs import (
    AGENT_COMMAND_LINE,
    PACKAGE_AGENT_VARIABLE,
    AgentProgramRefusalError,
    existing_profile_agent_root,
    hosted_python,
)

SIGN_IN_PROVIDERS: Final = ("claude", "codex", "antigravity")
"""The providers a console sign-in supports."""
DEVICE_PROVIDERS: Final = ("codex",)
"""The providers whose login has a device-code flow."""
REFUSAL_STATUS: Final = 2
"""The exit status of a sign-in refused before the agent runs."""


class ProviderLoginRefusalError(Exception):
    """The console sign-in cannot run; the message says why and what to do, and carries no credential."""


@dataclass(frozen=True, slots=True)
class ProviderLogin:
    """The agent program, arguments, directory and environment of one console sign-in."""

    executable: Path
    arguments: tuple[str, ...]
    directory: Path
    environment: dict[str, str]


def _bundled_agent(received: Mapping[str, str], interpreter: Path) -> Path:
    declared = received.get(PACKAGE_AGENT_VARIABLE)
    name = "cadrumo-agent.exe" if sys.platform == "win32" else "cadrumo-agent"
    image = Path(declared) if declared is not None else interpreter.parent / "bin" / name
    if not image.is_absolute() or not image.is_file():
        raise ProviderLoginRefusalError(
            "This installation has no bundled agent to sign in with. Run the command from an installed "
            "Cadrumo package, or sign in from the desktop application under Ajustes > Proveedores de IA."
        )
    return image


def _inside_git_project(path: Path) -> bool:
    return any((folder / ".git").exists() for folder in (path, *path.parents))


def prepare_provider_login(
    *,
    storage_root: Path,
    profile_id: UUID,
    provider: str,
    device: bool,
    received: Mapping[str, str] | None = None,
    interpreter: Path | None = None,
) -> ProviderLogin:
    """Return how to run the agent's login for the profile, or refuse with the reason.

    Raises:
        ProviderLoginRefusalError: The provider, flow, profile root or agent cannot be used.
    """
    environment = os.environ if received is None else received
    python = Path(sys.executable if interpreter is None else interpreter)
    if provider not in SIGN_IN_PROVIDERS:
        raise ProviderLoginRefusalError(
            f"Provider {provider!r} cannot be signed in by hand. Use one of: {', '.join(SIGN_IN_PROVIDERS)}."
        )
    if device and provider not in DEVICE_PROVIDERS:
        raise ProviderLoginRefusalError(f"--device is only available for {', '.join(DEVICE_PROVIDERS)}.")
    try:
        root = existing_profile_agent_root(storage_root, profile_id)
    except AgentProgramRefusalError as error:
        raise ProviderLoginRefusalError("The agent folder's key is unreadable; the agent cannot be located.") from error
    if root is None:
        raise ProviderLoginRefusalError(
            "The agent for this profile has not started yet. Open Cadrumo with this profile selected, "
            "then run this command again."
        )
    if _inside_git_project(root):
        raise ProviderLoginRefusalError(
            "The agent folder sits inside a Git project, which a provider sign-in refuses. "
            "Point CADRUMO_STORAGE_ROOT at a folder outside any Git project."
        )
    executable = _bundled_agent(environment, python)
    try:
        packaged_python = hosted_python(received=environment, interpreter=python)
    except AgentProgramRefusalError:
        packaged_python = None
    launch_environment = {**system_environment(os.environ), HOSTED_ROOT_VARIABLE: str(root)}
    external = agent_binary_directories(python=packaged_python, received=environment)
    if external is not None and external != "":
        launch_environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] = external
    return ProviderLogin(
        executable=executable,
        arguments=(*AGENT_COMMAND_LINE, "auth", "login", "--provider", provider, *(("--device",) if device else ())),
        directory=root,
        environment=launch_environment,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the sign-in with the caller's terminal and return the agent's exit status."""
    parser = argparse.ArgumentParser(prog="provider_login")
    parser.add_argument("--profile-id", type=UUID, required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--device", action="store_true")
    options = parser.parse_args(argv)
    try:
        launch = prepare_provider_login(
            storage_root=configured_storage_root(),
            profile_id=options.profile_id,
            provider=options.provider,
            device=options.device,
        )
    except ProviderLoginRefusalError as refusal:
        sys.stderr.write(f"{refusal}\n")
        return REFUSAL_STATUS
    # Inherited standard streams: the provider's login prints device codes there.
    done = subprocess.run(
        [str(launch.executable), *launch.arguments],
        cwd=launch.directory,
        env=launch.environment,
        check=False,
    )
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main())
