"""Smoke checks for a built Cadrumo distribution.

Run against an installed wheel to verify the package is importable, reports the
expected version, and exposes both of its working command-line surfaces: the
application and the MCP server that fronts it.

Usage from CI (``.github/workflows/publish.yml``)::

    uv run --isolated --no-project --find-links dist \
      --with "cadrumo==${VERSION}" dev/smoke/smoke_check.py

Not a pytest suite: functions are named ``check_*`` and the file is
``smoke_check.py`` so pytest never collects it, because the failure path here
is ``sys.exit(1)``, which would kill a pytest runner.

It runs on PATH in an ``--isolated --no-project`` environment whose only
project content is the artifact under test, so it must import nothing but the
standard library and the distribution it is checking.
"""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import subprocess
import sys
from typing import NoReturn

CLI_SCRIPT = "aeat"
MCP_SCRIPT = "cadrumo-mcp"
COMPANIONS = ("cadrumo-data-manuals", "cadrumo-data-official")

_TIMEOUT = 120


def _fail(message: str) -> NoReturn:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def _ok(message: str) -> None:
    print(f"ok: {message}")


def _run(name: str, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run a console script, falling back to ``python -m`` when not on PATH."""
    script = shutil.which(name)
    command = [script, *args] if script else [sys.executable, "-m", name.replace("-", "_"), *args]
    return subprocess.run(  # noqa: S603 - argv is built from module constants only.
        command,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        env={**os.environ, **(env or {})},
        check=False,
    )


def installed_version(distribution: str) -> str:
    """Return an installed distribution version, refusing instructively when absent.

    An absent distribution raises ``PackageNotFoundError``, which nothing here
    caught. This runs against an isolated environment whose only content is the
    artifact under test, so a companion corpus that failed to install is the
    likeliest packaging failure there is - and it is precisely what this check
    exists to catch. It surfaced as an unhandled traceback instead of the one
    FAIL line every other refusal in this file produces.
    """
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        _fail(f"{distribution} is not installed in this environment")


def check_metadata() -> str:
    """The distribution and its two pinned corpora are installed."""
    version = installed_version("cadrumo")
    for companion in COMPANIONS:
        companion_version = installed_version(companion)
        if companion_version != version:
            _fail(f"{companion} is {companion_version}, expected {version} to match cadrumo")
    _ok(f"cadrumo {version} installed with both corpora at the same version")
    return version


def check_import() -> None:
    """The package imports and exposes its version."""
    import cadrumo

    if not getattr(cadrumo, "__version__", ""):
        _fail("cadrumo.__version__ is missing or empty")
    _ok(f"cadrumo imports, __version__ = {cadrumo.__version__}")


def check_cli(version: str) -> None:
    """The CLI console script runs and reports the installed version."""
    result = _run(CLI_SCRIPT, ["--version"])
    if result.returncode != 0:
        _fail(f"{CLI_SCRIPT} --version exited {result.returncode}: {result.stderr.strip()[:400]}")
    if version not in result.stdout:
        _fail(f"{CLI_SCRIPT} --version did not report {version}: {result.stdout.strip()[:200]}")
    _ok(f"{CLI_SCRIPT} --version reports {version}")


def check_cli_help() -> None:
    """The command tree builds far enough to render root help.

    Asserts on the command tokens rather than the surrounding prose: help text
    is localized, the tokens are not.
    """
    result = _run(CLI_SCRIPT, ["--help"])
    if result.returncode != 0:
        _fail(f"{CLI_SCRIPT} --help exited {result.returncode}: {result.stderr.strip()[:400]}")
    for family in (f"{CLI_SCRIPT} config", f"{CLI_SCRIPT} app"):
        if family not in result.stdout:
            _fail(f"{CLI_SCRIPT} --help does not list the {family!r} command family")
    _ok(f"{CLI_SCRIPT} --help lists both root command families")


def check_mcp_script() -> None:
    """The second console script resolves and its server runtime shipped.

    ``--help`` proves the entry point is installed and reaches argparse, but it
    returns before the server is imported: ``main`` defers that import so an
    incomplete runtime refuses with an install hint instead of a traceback.
    Proving the artifact is actually serviceable therefore needs the deferred
    import attempted as well, which is why this reaches past the public surface.
    Starting the server itself is not an option here - it is a stdio transport
    and would block until its peer closed the stream.
    """
    result = _run(MCP_SCRIPT, ["--help"])
    if result.returncode != 0:
        _fail(f"{MCP_SCRIPT} --help exited {result.returncode}: {result.stderr.strip()[:400]}")
    if "--profile-secrets-file" not in result.stdout:
        _fail(f"{MCP_SCRIPT} --help does not offer --profile-secrets-file: {result.stdout.strip()[:200]}")
    imported = subprocess.run(
        [sys.executable, "-c", "from cadrumo_harness.mcp._server import serve; assert callable(serve)"],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        check=False,
    )
    if imported.returncode != 0:
        _fail(f"{MCP_SCRIPT} server runtime did not import: {imported.stderr.strip()[:400]}")
    _ok(f"{MCP_SCRIPT} resolves and its server runtime imports")


def main() -> int:
    """Run every check in order, failing the process on the first refusal."""
    version = check_metadata()
    check_import()
    check_cli(version)
    check_cli_help()
    check_mcp_script()
    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
