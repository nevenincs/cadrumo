"""Prove the built devcontainer image is actually usable, from inside it.

Run by ``just devcontainer-test`` as::

    docker run --rm cadrumo-devcontainer bash -lc "python dev/containers/devcontainer_smoke.py"

Why a script and not an inline ``python -c`` in the recipe: ``just`` runs plain
recipes through the platform shell, which is PowerShell on Windows, and
PowerShell parses ``<`` as a reserved operator and does not honour POSIX
backslash-quote escaping. An inline probe containing HTML and nested quotes died
at PARSE time on Windows before docker was ever invoked — the recipe failed
while saying nothing about the image. One file, one level of quoting, both
platforms.

The checks map one-to-one onto defects that shipped in this image:

* ``import cadrumo`` under a LOGIN shell — ``bash -lc`` re-runs ``/etc/profile``,
  which resets ``PATH`` and discarded the virtualenv, so ``python`` resolved to
  the system interpreter. Broke the VS Code integrated terminal too.
* ``just`` on ``PATH`` — the devcontainer ``postCreateCommand`` is
  ``just install && just env-setup``; without it the image builds and then
  fails at container creation.
* unit-test collection — the pre-warmed editable install resolves.
* a real headless Chromium LAUNCH — ``playwright install --dry-run`` only prints
  a download URL. It touches no shared libraries, so it stayed green straight
  through the Debian 13 ``t64`` library rename that broke the image.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if not __package__:
    __package__ = "dev.containers"

from ..ci.lane_reachability import resolve_just_executable  # noqa: E402

_VENV_ROOT = Path("/workspace/.venv")


def _check_interpreter() -> None:
    """Confirm a login shell resolves `python` to the project virtualenv.

    Tested via ``sys.prefix``, never ``Path(sys.executable).resolve()``: inside
    a virtualenv ``bin/python`` is a SYMLINK to the base interpreter, so
    resolving it reports ``/usr/local/bin/python3.13`` and the check fails on a
    perfectly healthy image. ``sys.prefix`` differing from ``sys.base_prefix``
    is the authoritative "am I in a venv" signal.
    """
    if sys.prefix == sys.base_prefix:
        raise SystemExit(
            f"FAIL: running outside a virtualenv (prefix {sys.prefix}).\n"
            "A login shell re-runs /etc/profile, which resets PATH; the image must declare "
            "the venv in /etc/profile.d as well as in ENV."
        )
    if Path(sys.prefix) != _VENV_ROOT:
        raise SystemExit(f"FAIL: virtualenv is {sys.prefix}, expected {_VENV_ROOT}.")

    # Separately confirm PATH ordering, which is what a login shell breaks.
    on_path = shutil.which("python")
    if on_path is None or _VENV_ROOT not in Path(on_path).parents:
        raise SystemExit(
            f"FAIL: `python` on PATH is {on_path}, not the virtualenv's. "
            "The /etc/profile.d PATH declaration is missing or ordered behind the system bin."
        )
    print(f"ok  interpreter          {on_path} (prefix {sys.prefix})")


def _check_project_import() -> None:
    """Confirm the pre-warmed editable install imports."""
    import cadrumo

    print(f"ok  import cadrumo       {cadrumo.__file__}")


def _check_just() -> None:
    """Confirm `just` is present for the devcontainer postCreateCommand."""
    try:
        executable = resolve_just_executable()
    except RuntimeError as error:
        raise SystemExit(
            "FAIL: `just` is not on PATH in the image, but devcontainer.json's "
            "postCreateCommand is `just install && just env-setup` — the image would "
            "build and then fail at container creation."
        ) from error
    completed = subprocess.run(  # noqa: S603 - `shutil.which`-resolved executable, fixed argv, no caller input
        [executable, "--version"], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise SystemExit(f"FAIL: `just` at {executable} is present but not runnable.")
    print(f"ok  just                 {completed.stdout.strip()}")


def _check_unit_collection() -> None:
    """Confirm the unit suite collects against the baked source tree."""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "unit"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit("FAIL: unit-test collection failed inside the image.")
    summary = completed.stdout.strip().splitlines()
    print(f"ok  unit collection      {summary[-1] if summary else 'collected'}")


def _check_chromium_launches() -> None:
    """Actually start headless Chromium and drive a page.

    This is the check that exercises the Dockerfile's explicit shared-library
    list. A missing lib surfaces here as a launch failure naming the object.
    """
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto("data:text/plain,cadrumo")
            if page.evaluate("1 + 1") != 2:
                raise SystemExit("FAIL: Chromium launched but could not evaluate JavaScript.")
            print(f"ok  chromium headless   {browser.version}")
        finally:
            browser.close()
    finally:
        playwright.stop()


def main() -> int:
    """Run every image check, failing loudly on the first defect."""
    _check_interpreter()
    _check_project_import()
    _check_just()
    _check_unit_collection()
    _check_chromium_launches()
    print("\ndevcontainer image verified: toolchain usable with no further provisioning.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
