"""Build and verify the core AEAT wheel using a plain pip-installed venv."""

from __future__ import annotations

import argparse
import sys
import venv
from pathlib import Path

from .smoke_core import (
    _assert_attachment_and_llm_surfaces,
    _assert_cli_smoke,
    _assert_installed_data,
    _assert_wheel_metadata_matches_pyproject,
    _build_wheel,
    _executable,
    _manifest_path,
    _run,
    _validate_frozen_exports,
    _venv_python,
    _work_dir,
    _write_smoke_manifest,
)


def _create_pip_venv(work_dir: Path, python_executable: str) -> Path:
    """Create a clean virtualenv with stdlib venv and install pip."""
    venv_path = work_dir / "pip-venv"
    builder = venv.EnvBuilder(with_pip=True, clear=False, symlinks=False)
    builder.create(venv_path)
    python = _venv_python(venv_path)
    version = _run([str(python), "--version"], cwd=work_dir)
    requested_major_minor = ".".join(python_executable.split(".")[:2])
    if python_executable[0].isdigit() and requested_major_minor not in version.stdout:
        raise SystemExit(
            f"pip venv interpreter {version.stdout.strip()!r} does not match requested {python_executable!r}"
        )
    return venv_path


def _install_target_with_pip(work_dir: Path, target: str, venv_path: Path) -> None:
    """Install one target specifier into a stdlib venv using pip only."""
    python = _venv_python(venv_path)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            target,
        ],
        cwd=work_dir,
    )
    _run([str(python), "-m", "pip", "check"], cwd=work_dir)


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
        "--skip-export-checks",
        action="store_true",
        help="Skip frozen uv export surface checks and run only the installed-wheel smoke.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    uv = _executable("uv")
    work_dir = _work_dir(repo_root, args.work_dir, prefix="pip-core")
    print(f"pip packaging smoke work dir: {work_dir}", flush=True)

    if not args.skip_export_checks:
        print("validating frozen dependency exports", flush=True)
        _validate_frozen_exports(repo_root, uv)

    print("building wheel", flush=True)
    wheel = _build_wheel(repo_root, work_dir, uv)
    _assert_wheel_metadata_matches_pyproject(repo_root, wheel)

    print("creating stdlib venv and installing wheel with pip", flush=True)
    venv_path = _create_pip_venv(work_dir, args.python)
    _install_artifact_with_pip(work_dir, wheel, venv_path)
    _assert_installed_data(work_dir, venv_path)
    _assert_attachment_and_llm_surfaces(work_dir, venv_path)
    _assert_cli_smoke(work_dir, venv_path)

    checks = [
        "wheel tracked shipped-data payload",
        "wheel metadata dependency surface",
        "stdlib venv creation",
        "plain pip wheel install",
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
        lane="pip-core-wheel",
        artifacts={
            "wheel": _manifest_path(work_dir, wheel),
            "venv": _manifest_path(work_dir, venv_path),
        },
        checks=tuple(checks),
        details={"python": args.python},
    )

    print(f"pip core packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
