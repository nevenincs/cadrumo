"""Build and verify the aggregate optional extras in a fresh pip venv."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .._paths import REPO_ROOT
from ._smoke_common import (
    assert_cadrumo_version_output,
    assert_installed_data,
    assert_wheel_contains_tracked_data,
    assert_wheel_metadata_matches_pyproject,
    create_pip_venv,
    expected_wheel_data_paths,
    install_targets_with_pip,
    isolated_product_env,
    record_proof,
    relative_manifest_path,
    require_executable,
    resolve_work_dir,
    run_checked,
    run_checked_marker,
    validate_frozen_exports,
    venv_cadrumo_path,
    venv_python_path,
    write_smoke_manifest,
)
from .python_cohort import (
    COHORT_STAMPED_WHEEL_DATA_PATHS,
    PythonCohort,
    assert_installed_cohort,
    install_targets,
    load_python_cohort,
)


def _install_all_extras_with_pip(
    work_dir: Path,
    cohort: PythonCohort,
    venv_path: Path,
) -> None:
    """Install the supplied root and companion artifacts through ``all``."""
    install_targets_with_pip(
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
    env = isolated_product_env(work_dir / "all-extras-import-state")
    run_checked_marker(
        [str(venv_python_path(venv_path)), "-c", code], cwd=work_dir, env=env, marker="all-extra-imports-ok"
    )
    record_proof("all capability-gated optional imports")


def _assert_cli_version(work_dir: Path, venv_path: Path) -> None:
    """Verify the installed console script starts in the all-extras venv."""
    env = isolated_product_env(work_dir / "cli-version-state")
    version = run_checked([str(venv_cadrumo_path(venv_path)), "--version"], cwd=work_dir, env=env)
    assert_cadrumo_version_output(version, context="in all-extras venv")
    record_proof("installed CLI version smoke")


def declared_claims(*, skip_export_checks: bool) -> tuple[str, ...]:
    """Return the claims this lane promises to prove, for its smoke manifest.

    The manifest refuses a declared claim whose assertion never ran, so this
    list and the lane body are one contract: skipping the export checks must
    drop their claim, or the run fails naming a claim with nothing behind it.

    Extracted so that coupling is provable without building a wheel, a venv
    and every optional extra - which is what this lane exists to install.
    """
    claims = [
        "wheel tracked shipped-data payload",
        "wheel metadata dependency surface",
        "stdlib venv creation",
        "exact local cohort install with pip",
        "pip dependency check",
        "installed bundled data resources",
        "all capability-gated optional imports",
        "installed CLI version smoke",
    ]
    if not skip_export_checks:
        claims.insert(0, "frozen dependency exports")
    return tuple(claims)


def build_parser() -> argparse.ArgumentParser:
    """Return the lane's argument parser, so its contract is testable alone."""
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
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the aggregate optional-extras installed-wheel packaging smoke gate."""
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = REPO_ROOT
    uv = require_executable("uv")
    work_dir = resolve_work_dir(repo_root, args.work_dir, prefix="extras")
    print(f"all-extras packaging smoke work dir: {work_dir}", flush=True)

    if not args.skip_export_checks:
        print("validating frozen dependency exports", flush=True)
        validate_frozen_exports(repo_root, uv)

    cohort = load_python_cohort(args.cohort_dir)
    wheel = cohort.root_wheel
    print("using supplied immutable Python cohort", flush=True)
    assert_wheel_contains_tracked_data(
        repo_root,
        wheel,
        expected_wheel_data_paths(repo_root) | COHORT_STAMPED_WHEEL_DATA_PATHS,
    )
    assert_wheel_metadata_matches_pyproject(repo_root, wheel)

    print("creating stdlib venv and installing wheel[all] with pip", flush=True)
    venv_path = create_pip_venv(work_dir, args.python)
    _install_all_extras_with_pip(work_dir, cohort, venv_path)
    assert_installed_cohort(
        venv_python_path(venv_path),
        cohort,
        root_artifact=wheel,
        cwd=work_dir,
    )
    assert_installed_data(work_dir, venv_path)
    _assert_all_extra_imports(work_dir, venv_path)
    _assert_cli_version(work_dir, venv_path)

    declared = declared_claims(skip_export_checks=args.skip_export_checks)
    manifest = write_smoke_manifest(
        work_dir,
        lane="all-extras-wheel",
        artifacts={
            "wheel": relative_manifest_path(work_dir, wheel),
            "data_wheel_manuals": relative_manifest_path(work_dir, cohort.manuals_wheel),
            "data_wheel_official": relative_manifest_path(work_dir, cohort.official_wheel),
            "venv": relative_manifest_path(work_dir, venv_path),
        },
        declared=tuple(declared),
        details={"cohort_version": cohort.version, "python": args.python},
    )

    print(f"all-extras packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
