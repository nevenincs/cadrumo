"""Build and verify the core AEAT wheel using a plain pip-installed venv."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .._paths import REPO_ROOT
from ._smoke_common import (
    assert_attachment_and_llm_surfaces,
    assert_cli_smoke,
    assert_installed_data,
    assert_wheel_contains_tracked_data,
    assert_wheel_metadata_matches_pyproject,
    create_pip_venv,
    expected_wheel_data_paths,
    install_targets_with_pip,
    relative_manifest_path,
    require_executable,
    resolve_work_dir,
    validate_frozen_exports,
    venv_python_path,
    write_smoke_manifest,
)
from .python_cohort import (
    COHORT_STAMPED_WHEEL_DATA_PATHS,
    assert_installed_cohort,
    install_targets,
    load_python_cohort,
)


def _install_target_with_pip(work_dir: Path, target: str, venv_path: Path) -> None:
    """Install one target specifier into a stdlib venv using pip only."""
    install_targets_with_pip(work_dir, (target,), venv_path)


def _install_artifact_with_pip(work_dir: Path, artifact: Path, venv_path: Path) -> None:
    """Install one built distribution artifact into a stdlib venv using pip only."""
    _install_target_with_pip(work_dir, str(artifact.resolve()), venv_path)


def main(argv: list[str] | None = None) -> int:
    """Run the pip-installed core wheel packaging smoke gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        default=f"{sys.version_info.major}.{sys.version_info.minor}",
        help="Expected Python major.minor for the stdlib venv.",
    )
    parser.add_argument("--work-dir", help="Empty directory for wheel, venv, and profile smoke artifacts.")
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

    repo_root = REPO_ROOT
    uv = require_executable("uv")
    work_dir = resolve_work_dir(repo_root, args.work_dir, prefix="pip-core")
    print(f"pip packaging smoke work dir: {work_dir}", flush=True)

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

    print("creating stdlib venv and installing the exact cohort with pip", flush=True)
    venv_path = create_pip_venv(work_dir, args.python)
    install_targets_with_pip(
        work_dir,
        install_targets(cohort, root_artifact=wheel),
        venv_path,
    )
    assert_installed_cohort(
        venv_python_path(venv_path),
        cohort,
        root_artifact=wheel,
        cwd=work_dir,
    )
    assert_installed_data(work_dir, venv_path)
    assert_attachment_and_llm_surfaces(work_dir, venv_path)
    assert_cli_smoke(work_dir, venv_path)

    declared = [
        "wheel tracked shipped-data payload",
        "wheel metadata dependency surface",
        "stdlib venv creation",
        "exact local cohort install with pip",
        "pip dependency check",
        "installed bundled data resources",
        "attachment storage round-trip",
        "core LLM missing-extra boundary",
        "installed CLI config/profile smoke",
    ]
    if not args.skip_export_checks:
        declared.insert(0, "frozen dependency exports")
    manifest = write_smoke_manifest(
        work_dir,
        lane="pip-core-wheel",
        artifacts={
            "wheel": relative_manifest_path(work_dir, wheel),
            "data_wheel_manuals": relative_manifest_path(work_dir, cohort.manuals_wheel),
            "data_wheel_official": relative_manifest_path(work_dir, cohort.official_wheel),
            "venv": relative_manifest_path(work_dir, venv_path),
        },
        declared=tuple(declared),
        details={"cohort_version": cohort.version, "python": args.python},
    )

    print(f"pip core packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
