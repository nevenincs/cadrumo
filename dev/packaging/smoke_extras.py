"""Build and verify the aggregate optional extras in a fresh pip venv."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .python_cohort import (
    COHORT_STAMPED_WHEEL_DATA_PATHS,
    PythonCohort,
    assert_installed_cohort,
    install_targets,
    load_python_cohort,
)
from .smoke_core import (
    _assert_cadrumo_version_output,
    _assert_installed_data,
    _assert_wheel_contains_tracked_data,
    _assert_wheel_metadata_matches_pyproject,
    _clean_product_env,
    _executable,
    _expected_wheel_data_paths,
    _manifest_path,
    _run,
    _validate_frozen_exports,
    _venv_bin,
    _venv_python,
    _work_dir,
    _write_smoke_manifest,
)
from .smoke_pip_core import _create_pip_venv, _install_targets_with_pip


def _install_all_extras_with_pip(
    work_dir: Path,
    cohort: PythonCohort,
    venv_path: Path,
) -> None:
    """Install the supplied root and companion artifacts through ``all``."""
    _install_targets_with_pip(
        work_dir,
        install_targets(cohort, root_artifact=cohort.root_wheel, extras=("all",)),
        venv_path,
    )


def _assert_all_extra_imports(work_dir: Path, venv_path: Path) -> None:
    """Verify all capability-gated optional packages import in the installed venv."""
    code = """
import anthropic
import google_auth_oauthlib.flow
import googleapiclient.discovery
import playwright.async_api
import playwright_stealth

from cadrumo.core import ANTHROPIC_EXTRA, BROWSER_EXTRA, GOOGLE_EXTRA, require_optional_extra

for extra in (GOOGLE_EXTRA, BROWSER_EXTRA, ANTHROPIC_EXTRA):
    require_optional_extra(extra)

print("all-extra-imports-ok")
"""
    runtime_root = work_dir / "all-extras-import-state"
    env = {
        **_clean_product_env(),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(runtime_root),
        "CADRUMO_DATABASE_URL": f"sqlite:///{(runtime_root / 'cadrumo.db').as_posix()}",
    }
    _run([str(_venv_python(venv_path)), "-c", code], cwd=work_dir, env=env)


def _assert_cli_version(work_dir: Path, venv_path: Path) -> None:
    """Verify the installed console script starts in the all-extras venv."""
    runtime_root = work_dir / "cli-version-state"
    env = {
        **_clean_product_env(),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(runtime_root),
        "CADRUMO_DATABASE_URL": f"sqlite:///{(runtime_root / 'cadrumo.db').as_posix()}",
    }
    executable = "aeat.exe" if sys.platform == "win32" else "aeat"
    version = _run([str(_venv_bin(venv_path) / executable), "--version"], cwd=work_dir, env=env)
    _assert_cadrumo_version_output(version, context="in all-extras venv")


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
        "--cohort-dir",
        required=True,
        type=Path,
        help="Directory containing the prebuilt immutable Python cohort.",
    )
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

    cohort = load_python_cohort(args.cohort_dir)
    wheel = cohort.root_wheel
    print("using supplied immutable Python cohort", flush=True)
    _assert_wheel_contains_tracked_data(
        repo_root,
        wheel,
        _expected_wheel_data_paths(repo_root) | COHORT_STAMPED_WHEEL_DATA_PATHS,
    )
    _assert_wheel_metadata_matches_pyproject(repo_root, wheel)

    print("creating stdlib venv and installing wheel[all] with pip", flush=True)
    venv_path = _create_pip_venv(work_dir, args.python)
    _install_all_extras_with_pip(work_dir, cohort, venv_path)
    assert_installed_cohort(
        _venv_python(venv_path),
        cohort,
        root_artifact=wheel,
        cwd=work_dir,
    )
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
            "data_wheel_manuals": _manifest_path(work_dir, cohort.manuals_wheel),
            "data_wheel_official": _manifest_path(work_dir, cohort.official_wheel),
            "venv": _manifest_path(work_dir, venv_path),
        },
        checks=tuple(checks),
        details={"cohort_version": cohort.version, "python": args.python},
    )

    print(f"all-extras packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
