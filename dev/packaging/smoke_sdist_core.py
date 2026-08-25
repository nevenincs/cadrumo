"""Build and verify the AEAT source distribution through plain pip install."""

from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path

from .._paths import REPO_ROOT
from ._smoke_common import (
    assert_attachment_and_llm_surfaces,
    assert_cli_smoke,
    assert_installed_data,
    create_pip_venv,
    install_targets_with_pip,
    record_proof,
    relative_manifest_path,
    require_executable,
    resolve_work_dir,
    tracked_source_data_paths,
    validate_frozen_exports,
    venv_python_path,
    write_smoke_manifest,
)
from .python_cohort import (
    assert_installed_cohort,
    install_targets,
    load_python_cohort,
)


def _assert_sdist_contains_data(repo_root: Path, sdist: Path) -> None:
    """Verify every tracked shipped-data file appears in the source distribution."""
    expected = tracked_source_data_paths(repo_root)
    _assert_sdist_contains_expected_data(sdist, expected)


def _assert_sdist_contains_expected_data(sdist: Path, expected: set[str]) -> None:
    """Verify expected runtime data is present and companion-owned bytes are absent."""
    with tarfile.open(sdist, "r:gz") as archive:
        names = set(archive.getnames())
    missing = sorted(path for path in expected if not any(name.endswith(f"/{path}") for name in names))
    if missing:
        raise SystemExit(f"sdist is missing {len(missing)} tracked shipped-data files; first ten: {missing[:10]!r}")
    leaked = sorted(
        name
        for name in names
        if "/src/cadrumo/_data/corpus/" in name
        and name.lower().endswith((".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip"))
    )
    if leaked:
        raise SystemExit(
            f"root sdist leaked {len(leaked)} companion-owned corpus binaries; first ten: {leaked[:10]!r}",
        )
    record_proof("tracked shipped-data source preflight")
    record_proof("sdist tracked shipped-data payload")


def main(argv: list[str] | None = None) -> int:
    """Run the sdist-installed core packaging smoke gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        default=f"{sys.version_info.major}.{sys.version_info.minor}",
        help="Expected Python major.minor for the stdlib venv.",
    )
    parser.add_argument("--work-dir", help="Empty directory for sdist, venv, and profile smoke artifacts.")
    parser.add_argument(
        "--cohort-dir",
        required=True,
        type=Path,
        help="Directory containing the prebuilt root sdist and companion wheels.",
    )
    parser.add_argument(
        "--skip-export-checks",
        action="store_true",
        help="Skip frozen uv export surface checks and run only the installed-sdist smoke.",
    )
    args = parser.parse_args(argv)

    repo_root = REPO_ROOT
    uv = require_executable("uv")
    work_dir = resolve_work_dir(repo_root, args.work_dir, prefix="sdist-core")
    print(f"sdist packaging smoke work dir: {work_dir}", flush=True)

    if not args.skip_export_checks:
        print("validating frozen dependency exports", flush=True)
        validate_frozen_exports(repo_root, uv)

    cohort = load_python_cohort(args.cohort_dir)
    print("using supplied immutable sdist cohort", flush=True)
    expected_data_paths = {
        path
        for path in tracked_source_data_paths(repo_root)
        if not (
            path.startswith("src/cadrumo/_data/corpus/")
            and path.lower().endswith((".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip"))
        )
        and "/tests/" not in path
    }
    sdist = cohort.root_sdist
    _assert_sdist_contains_expected_data(sdist, expected_data_paths)

    print("creating stdlib venv and installing sdist plus exact companions", flush=True)
    venv_path = create_pip_venv(work_dir, args.python)
    install_targets_with_pip(
        work_dir,
        install_targets(cohort, root_artifact=sdist),
        venv_path,
    )
    assert_installed_cohort(
        venv_python_path(venv_path),
        cohort,
        root_artifact=sdist,
        cwd=work_dir,
    )
    assert_installed_data(work_dir, venv_path)
    assert_attachment_and_llm_surfaces(work_dir, venv_path)
    assert_cli_smoke(work_dir, venv_path)

    declared = [
        "tracked shipped-data source preflight",
        "sdist tracked shipped-data payload",
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
        lane="sdist-core",
        artifacts={
            "sdist": relative_manifest_path(work_dir, sdist),
            "data_wheel_manuals": relative_manifest_path(work_dir, cohort.manuals_wheel),
            "data_wheel_official": relative_manifest_path(work_dir, cohort.official_wheel),
            "venv": relative_manifest_path(work_dir, venv_path),
        },
        declared=tuple(declared),
        details={"cohort_version": cohort.version, "python": args.python},
    )

    print(f"sdist core packaging smoke passed: {sdist}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
