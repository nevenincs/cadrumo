"""Build and verify the aggregate optional extras in a fresh pip venv."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .smoke_core import (
    _assert_installed_data,
    _assert_wheel_metadata_matches_pyproject,
    _build_wheel,
    _executable,
    _manifest_path,
    _run,
    _validate_frozen_exports,
    _venv_aeat,
    _venv_python,
    _work_dir,
    _write_smoke_manifest,
)
from .smoke_pip_core import _create_pip_venv, _install_target_with_pip


def _install_all_extras_with_pip(work_dir: Path, wheel: Path, venv_path: Path) -> None:
    """Install the built wheel through the public ``all`` extra."""
    target = f"aeat[all] @ {wheel.resolve().as_uri()}"
    _install_target_with_pip(work_dir, target, venv_path)


def _assert_all_extra_imports(work_dir: Path, venv_path: Path) -> None:
    """Verify all capability-gated optional packages import in the installed venv."""
    code = """
import anthropic
import google_auth_oauthlib.flow
import googleapiclient.discovery
import playwright.async_api
import playwright_stealth

from aeat.core import ANTHROPIC_EXTRA, BROWSER_EXTRA, GOOGLE_EXTRA, require_optional_extra

for extra in (GOOGLE_EXTRA, BROWSER_EXTRA, ANTHROPIC_EXTRA):
    require_optional_extra(extra)

print("all-extra-imports-ok")
"""
    _run([str(_venv_python(venv_path)), "-c", code], cwd=work_dir)


def _assert_cli_version(work_dir: Path, venv_path: Path) -> None:
    """Verify the installed console script starts in the all-extras venv."""
    version = _run([str(_venv_aeat(venv_path)), "--version"], cwd=work_dir)
    if "aeat " not in version.stdout:
        raise SystemExit(f"unexpected aeat --version output in all-extras venv: {version.stdout!r}")


def main(argv: list[str] | None = None) -> int:
    """Run the aggregate optional-extras installed-wheel packaging smoke gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        default=f"{sys.version_info.major}.{sys.version_info.minor}",
        help="Expected Python major.minor for the stdlib venv.",
    )
    parser.add_argument("--work-dir", help="Empty directory for wheel, venv, and optional-extra artifacts.")
    parser.add_argument(
        "--skip-export-checks",
        action="store_true",
        help="Skip frozen uv export surface checks and run only the installed-wheel smoke.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    uv = _executable("uv")
    work_dir = _work_dir(repo_root, args.work_dir, prefix="extras")
    print(f"all-extras packaging smoke work dir: {work_dir}", flush=True)

    if not args.skip_export_checks:
        print("validating frozen dependency exports", flush=True)
        _validate_frozen_exports(repo_root, uv)

    print("building wheel", flush=True)
    wheel = _build_wheel(repo_root, work_dir, uv)
    _assert_wheel_metadata_matches_pyproject(repo_root, wheel)

    print("creating stdlib venv and installing wheel[all] with pip", flush=True)
    venv_path = _create_pip_venv(work_dir, args.python)
    _install_all_extras_with_pip(work_dir, wheel, venv_path)
    _assert_installed_data(work_dir, venv_path)
    _assert_all_extra_imports(work_dir, venv_path)
    _assert_cli_version(work_dir, venv_path)

    checks = [
        "wheel tracked shipped-data payload",
        "wheel metadata dependency surface",
        "stdlib venv creation",
        "plain pip wheel[all] install",
        "pip check",
        "installed bundled data resources",
        "all capability-gated optional imports",
        "installed CLI version smoke",
    ]
    if not args.skip_export_checks:
        checks.insert(0, "frozen dependency exports")
    manifest = _write_smoke_manifest(
        work_dir,
        lane="all-extras-wheel",
        artifacts={
            "wheel": _manifest_path(work_dir, wheel),
            "venv": _manifest_path(work_dir, venv_path),
        },
        checks=tuple(checks),
        details={"python": args.python},
    )

    print(f"all-extras packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
