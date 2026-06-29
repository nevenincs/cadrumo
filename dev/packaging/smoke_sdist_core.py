"""Build and verify the AEAT source distribution through plain pip install."""

from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path

from .smoke_core import (
    _assert_attachment_and_llm_surfaces,
    _assert_cli_smoke,
    _assert_installed_data,
    _executable,
    _manifest_path,
    _run,
    _tracked_source_data_paths,
    _validate_frozen_exports,
    _work_dir,
    _write_smoke_manifest,
)
from .smoke_pip_core import _create_pip_venv, _install_artifact_with_pip


def _build_sdist(repo_root: Path, work_dir: Path, uv: str) -> Path:
    """Build the AEAT source distribution into the smoke work directory."""
    sdist_dir = work_dir / "sdist"
    sdist_dir.mkdir(parents=True, exist_ok=True)
    _run([uv, "build", "--sdist", "--out-dir", str(sdist_dir)], cwd=repo_root)
    sdists = sorted(sdist_dir.glob("aeat-*.tar.gz"))
    if len(sdists) != 1:
        raise SystemExit(f"expected exactly one aeat sdist in {sdist_dir}; got {[sdist.name for sdist in sdists]!r}")
    return sdists[0]


def _assert_sdist_contains_data(repo_root: Path, sdist: Path) -> None:
    """Verify every tracked shipped-data file appears in the source distribution."""
    expected = _tracked_source_data_paths(repo_root)
    _assert_sdist_contains_expected_data(sdist, expected)


def _assert_sdist_contains_expected_data(sdist: Path, expected: set[str]) -> None:
    """Verify every expected shipped-data path appears in the source distribution."""
    with tarfile.open(sdist, "r:gz") as archive:
        names = set(archive.getnames())
    missing = sorted(path for path in expected if not any(name.endswith(f"/{path}") for name in names))
    if missing:
        raise SystemExit(f"sdist is missing {len(missing)} tracked shipped-data files; first ten: {missing[:10]!r}")


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

    print("building sdist", flush=True)
    expected_data_paths = _tracked_source_data_paths(repo_root)
    sdist = _build_sdist(repo_root, work_dir, uv)
    _assert_sdist_contains_expected_data(sdist, expected_data_paths)

    print("creating stdlib venv and installing sdist with pip", flush=True)
    venv_path = _create_pip_venv(work_dir, args.python)
    _install_artifact_with_pip(work_dir, sdist, venv_path)
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
            "venv": _manifest_path(work_dir, venv_path),
        },
        checks=tuple(checks),
        details={"python": args.python},
    )

    print(f"sdist core packaging smoke passed: {sdist}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
