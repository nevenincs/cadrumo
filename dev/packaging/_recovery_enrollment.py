"""Headless recovery enrollment for a spawned installed ``aeat`` CLI.

``config profile create`` enrolls recovery for every profile it publishes and
never falls through to a password-only record. A caller with no controlling
terminal must therefore take delivery of the recovery phrase on one bounded
writable descriptor and return the exact phrase on a second bounded readable
descriptor before the registration transaction publishes. There is no flag
that skips the exchange, and a probe that drives the real product has no
business wanting one: the possession proof is part of what "this build creates
a usable profile" means.

Handing those descriptors to a *child* process is where the platforms part.
POSIX inherits numeric descriptors, so the child is the ``aeat`` executable
itself and the numbers it is told are its own. Windows has no equivalent -
``subprocess`` refuses ``pass_fds`` there - and a CRT descriptor number is
meaningless in a new process. What transfers is the underlying HANDLE, and the
product ships the wrapper that converts an allowlisted HANDLE back into a
descriptor inside the child before dispatching the identical command. Windows
therefore reaches the CLI through the interpreter beside it rather than
through the executable directly.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ..scripted_registration_channels import scripted_registration_descriptors

#: The product's own inherited-HANDLE bootstrap. It converts ownership of the
#: allowlisted HANDLEs to CRT descriptors, injects the canonical descriptor
#: options, and dispatches the ordinary CLI in the same process.
WINDOWS_BOOTSTRAP_MODULE: Final[str] = "cadrumo.entrypoints.cli._windows_profile_secret_bootstrap"


class RecoveryEnrollmentError(RuntimeError):
    """Raised when no headless enrollment channel can be established."""


@dataclass(frozen=True)
class RecoveryEnrollmentInvocation:
    """One shaped invocation that carries a live enrollment channel."""

    argv: tuple[str, ...]
    inherited_descriptors: tuple[int, ...]


def windows_bootstrap_interpreter(cli: Path) -> Path:
    """Resolve the interpreter beside an installed CLI that can host the bootstrap.

    A console-script executable cannot convert an inherited HANDLE, so on
    Windows the bootstrap module is what actually runs. It has to be reached
    through the same environment the executable belongs to, which is the
    interpreter sharing its directory.
    """
    interpreter = cli.with_name("python.exe")
    try:
        return interpreter.resolve(strict=True)
    except OSError as error:
        raise RecoveryEnrollmentError(
            f"no interpreter beside the installed CLI to host the recovery bootstrap: {interpreter}",
        ) from error


def shape_enrollment_invocation(
    *,
    cli: Path,
    arguments: Sequence[str],
    handoff: int,
    verification: int,
) -> RecoveryEnrollmentInvocation:
    """Shape one invocation that tells a child about an existing channel.

    ``arguments`` is the ordinary ``aeat`` argument tail, without the
    executable and without either descriptor option: which options carry the
    channel, and which process is spawned to receive it, is exactly what
    differs by platform and is decided here. Who is on the other end of the
    two descriptors is the caller's business.
    """
    if sys.platform == "win32":
        import msvcrt

        return RecoveryEnrollmentInvocation(
            argv=(
                str(windows_bootstrap_interpreter(cli)),
                "-m",
                WINDOWS_BOOTSTRAP_MODULE,
                "--recovery-handoff-handle",
                str(msvcrt.get_osfhandle(handoff)),
                "--recovery-verification-handle",
                str(msvcrt.get_osfhandle(verification)),
                "--",
                *arguments,
            ),
            inherited_descriptors=(handoff, verification),
        )
    return RecoveryEnrollmentInvocation(
        argv=(
            str(cli),
            *arguments,
            "--recovery-handoff-fd",
            str(handoff),
            "--recovery-verification-fd",
            str(verification),
        ),
        inherited_descriptors=(handoff, verification),
    )


@contextmanager
def enrolled_profile_creation(*, cli: Path, arguments: Sequence[str]) -> Iterator[RecoveryEnrollmentInvocation]:
    """Yield a profile-creation invocation whose recovery exchange will complete."""
    with scripted_registration_descriptors() as (handoff, verification):
        yield shape_enrollment_invocation(
            cli=cli,
            arguments=arguments,
            handoff=handoff,
            verification=verification,
        )


__all__ = [
    "WINDOWS_BOOTSTRAP_MODULE",
    "RecoveryEnrollmentError",
    "RecoveryEnrollmentInvocation",
    "enrolled_profile_creation",
    "shape_enrollment_invocation",
    "windows_bootstrap_interpreter",
]
