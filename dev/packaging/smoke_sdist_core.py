"""Build and verify the AEAT source distribution through plain pip install."""

from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path

from .python_cohort import (
    assert_installed_cohort,
    install_targets,
    load_python_cohort,
)
from .smoke_core import (
    _assert_attachment_and_llm_surfaces,
    _assert_cli_smoke,
    _assert_installed_data,
    _executable,
    _manifest_path,
    _run,
    _tracked_source_data_paths,
    _validate_frozen_exports,
    _venv_python,
    _work_dir,
    _write_smoke_manifest,
)
from .smoke_pip_core import _create_pip_venv, _install_targets_with_pip


def _build_sdist(work_dir: Path, uv: str, *, build_root: Path) -> Path:
    """Build the Cadrumo source distribution into the smoke work directory.

    Built from ``build_root`` so the sdist corresponds to a commit rather than
    to whatever the shared worktree happened to hold; pass a
    :func:`~dev.packaging.smoke_core._head_extract` tree. This is the lane that
    caught a torn peer edit live, shipping an sdist whose
    ``application/aggregation`` import did not resolve against its own
    ``_source_mesh`` and failing as if it were a packaging regression.
    """
    sdist_dir = work_dir / "sdist"
    sdist_dir.mkdir(parents=True, exist_ok=True)
    _run([uv, "build", "--sdist", "--out-dir", str(sdist_dir)], cwd=build_root)
    sdists = sorted(sdist_dir.glob("cadrumo-*.tar.gz"))
    if len(sdists) != 1:
        names = [sdist.name for sdist in sdists]
        raise SystemExit(f"expected exactly one cadrumo sdist in {sdist_dir}; got {names!r}")
    return sdists[0]


def _assert_sdist_contains_data(repo_root: Path, sdist: Path) -> None:
    """Verify every tracked shipped-data file appears in the source distribution."""
    expected = _tracked_source_data_paths(repo_root)
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

    repo_root = Path(__file__).resolve().parents[2]
    uv = _executable("uv")
    work_dir = _work_dir(repo_root, args.work_dir, prefix="sdist-core")
    print(f"sdist packaging smoke work dir: {work_dir}", flush=True)

    if not args.skip_export_checks:
        print("validating frozen dependency exports", flush=True)
        _validate_frozen_exports(repo_root, uv)

    cohort = load_python_cohort(args.cohort_dir)
    print("using supplied immutable sdist cohort", flush=True)
    expected_data_paths = {
        path
        for path in _tracked_source_data_paths(repo_root)
        if not (
            path.startswith("src/cadrumo/_data/corpus/")
            and path.lower().endswith((".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip"))
        )
        and "/tests/" not in path
    }
    sdist = cohort.root_sdist
    _assert_sdist_contains_expected_data(sdist, expected_data_paths)

    print("creating stdlib venv and installing sdist plus exact companions", flush=True)
    venv_path = _create_pip_venv(work_dir, args.python)
    _install_targets_with_pip(
        work_dir,
        install_targets(cohort, root_artifact=sdist),
        venv_path,
    )
    assert_installed_cohort(
        _venv_python(venv_path),
        cohort,
        root_artifact=sdist,
        cwd=work_dir,
    )
    _assert_installed_data(work_dir, venv_path)
    _assert_attachment_and_llm_surfaces(work_dir, venv_path)
    _assert_cli_smoke(work_dir, venv_path)

    checks = [
        "tracked shipped-data source preflight",
        "sdist tracked shipped-data payload",
        "stdlib venv creation",
        "plain pip sdist install",
        "pip check",
        "installed bundled data resources",
        "attachment storage round-trip",
        "core LLM missing-extra boundary",
        "installed CLI config/profile smoke",
    ]
    if not args.skip_export_checks:
        checks.insert(0, "frozen dependency exports")
    manifest = _write_smoke_manifest(
        work_dir,
        lane="sdist-core",
        artifacts={
            "sdist": _manifest_path(work_dir, sdist),
            "data_wheel_manuals": _manifest_path(work_dir, cohort.manuals_wheel),
            "data_wheel_official": _manifest_path(work_dir, cohort.official_wheel),
            "venv": _manifest_path(work_dir, venv_path),
        },
        checks=tuple(checks),
        details={"cohort_version": cohort.version, "python": args.python},
    )

    print(f"sdist core packaging smoke passed: {sdist}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
