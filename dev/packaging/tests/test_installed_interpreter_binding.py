"""The attested interpreter is the one the installed launcher actually runs.

An installer writes each console script naming the interpreter of the
environment it installed into, and on POSIX that name is an absolute symlink to
the base installation the environment was built from. The link *is* the
environment: behind it there is no adjacent ``pyvenv.cfg``, so an interpreter
reached by dereferencing it starts on the base ``sys.prefix`` and reports every
installed distribution as absent. Windows hides the distinction because its
launchers sit beside a copied ``python.exe``, so the same dereference is a no-op
there and only the POSIX legs observe it.

These cases pin the attested interpreter to the environment that owns the
launcher, prove a genuine install of the sealed wheel attests equal to that
wheel, and prove the attestation still separates that install from one whose
installed bytes have since moved.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from .._acquire_common import venv_bin_dir, venv_executable
from .._installed_wheel_binding import (
    installed_distribution_payload_sha256,
    installed_python_for_cli,
    sealed_wheel_payload_sha256,
)
from ._release_cohort_support import _real_product_wheel, _uv_executable, client_venv_template

# Serial and integration for the same reason as the sibling evidence suite:
# these cases install the real product wheel into a real environment, which is
# filesystem and subprocess work rather than quick-feedback unit work.
pytestmark = [pytest.mark.integration, pytest.mark.serial, pytest.mark.hex_core]

_UV_ENVIRONMENT = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}


def _install_product_wheel(root: Path) -> Path:
    """Install the real product wheel into its own fresh environment.

    A tamper case needs an environment it may write to, and the shared template
    is read by every other case in this package, so this builds a private one
    rather than copying the template. The wheel itself is still the one
    :func:`_real_product_wheel` builds once per process, so no second wheel-
    building path appears; only the environment is new.
    """
    venv = root / ".venv"
    uv = _uv_executable()
    interpreter = venv_bin_dir(venv) / ("python.exe" if os.name == "nt" else "python")
    for argv in (
        [uv, "venv", "--python", sys.executable, str(venv)],
        [uv, "pip", "install", "--python", str(interpreter), str(_real_product_wheel())],
    ):
        completed = subprocess.run(  # noqa: S603 - fixed uv argv over fixture-owned paths.
            argv,
            check=False,
            capture_output=True,
            text=True,
            env=_UV_ENVIRONMENT,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"tamper-case environment build failed: {argv!r}\n{completed.stderr}")
    return venv


def _displace_one_installed_file(cli: Path) -> Path:
    """Change one installed file's bytes without writing through a shared inode.

    An installer places files as hard links into its own cache, so writing to
    an installed path in place would rewrite the cached original and every
    other environment linked to it. Unlinking first drops only this
    environment's directory entry and leaves the shared inode intact.
    """
    target = cli.parent.parent / "Lib" if os.name == "nt" else cli.parent.parent / "lib"
    matches = sorted(target.glob("**/cadrumo/__init__.py"))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one installed cadrumo package root: {matches!r}")
    installed = matches[0]
    original = installed.read_bytes()
    installed.unlink()
    installed.write_bytes(original + b"\n")
    return installed


def test_attested_interpreter_stays_inside_the_launcher_environment() -> None:
    """The interpreter an installed launcher names owns that launcher's environment."""
    template = client_venv_template()
    cli = venv_executable(template, "aeat").resolve(strict=True)

    interpreter = installed_python_for_cli(cli)

    bin_dir = interpreter.parent.resolve(strict=True)
    assert bin_dir == cli.parent, f"attested interpreter {interpreter} left the launcher's own directory {cli.parent}"
    assert (bin_dir.parent / "pyvenv.cfg").is_file(), (
        f"attested interpreter {interpreter} has no environment marker beside it"
    )


def test_a_genuine_install_attests_equal_to_the_sealed_wheel_and_refuses_displaced_bytes(
    tmp_path: Path,
) -> None:
    """A real install of the sealed wheel attests to it, and stops attesting once it moves."""
    venv = _install_product_wheel(tmp_path)
    cli = venv_executable(venv, "aeat").resolve(strict=True)
    sealed = sealed_wheel_payload_sha256(_real_product_wheel())

    installed = installed_distribution_payload_sha256(cli, "cadrumo")
    assert installed == sealed, "a genuine install of the sealed wheel must attest to that wheel"

    displaced = _displace_one_installed_file(cli)

    after = installed_distribution_payload_sha256(cli, "cadrumo")
    assert after != sealed, f"the attestation accepted a displaced {displaced.name} as the sealed payload"
