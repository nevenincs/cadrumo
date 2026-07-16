"""Prove the mandatory three-wheel Cadrumo installation cohort.

The command-bearing ``cadrumo`` wheel excludes large corpus source binaries,
while two exact-version mandatory dependencies carry them:
``cadrumo-data-manuals`` owns ``corpus/manuals`` and
``cadrumo-data-official`` owns ``corpus/aeat_official`` plus
``corpus/normatives``. Both contribute to the same ``cadrumo_data`` implicit
namespace package.

This lane builds all three wheels from one pristine source snapshot, installs
them together into a fresh stdlib venv, proves their versions and root metadata
form one exact cohort, and runs full byte-exact registry verification. There is
no supported command-bearing installation without both data distributions.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Final

from .installed_tax_oracle import run_installed_tax_oracle
from .python_cohort import assert_installed_cohort, load_python_cohort
from .smoke_core import (
    _clean_product_env,
    _manifest_path,
    _run,
    _venv_bin,
    _venv_python,
    _work_dir,
    _write_smoke_manifest,
)
from .smoke_pip_core import _create_pip_venv

_CORPUS_BINARY_SUFFIXES = (".docx", ".pdf", ".xls", ".xlsx", ".zip")
_UTF_8: Final[str] = "utf-8"

_COHORT_PROBE = """
from importlib.metadata import requires, version

from cadrumo.domain.calculations.registry import bundled_authority

root_version = version("cadrumo")
expected = {
    f"cadrumo-data-manuals=={root_version}",
    f"cadrumo-data-official=={root_version}",
}
declared = set(requires("cadrumo") or ())
missing_requirements = expected - declared
if missing_requirements:
    raise SystemExit(f"root metadata lost mandatory companion pins: {sorted(missing_requirements)!r}")
for distribution in ("cadrumo-data-manuals", "cadrumo-data-official"):
    observed = version(distribution)
    if observed != root_version:
        raise SystemExit(f"{distribution} version {observed!r} != root version {root_version!r}")

authority = bundled_authority()
authority.validate_registry()
print(f"three-wheel-cohort-ok: {root_version}")
"""


def _head_extract(repo_root: Path, work_dir: Path) -> Path:
    """Extract a pristine ``git archive HEAD`` tree to build the lane's wheels from.

    A working tree may carry uncommitted changes (including registry TOML
    mid-edits) that a tree-built wheel would sweep into this lane's
    registry-validation probes, failing them for reasons outside the split
    contract. Building from the HEAD archive keeps the proof clean of
    uncommitted state; on a clean checkout (CI) it is identical to the tree.
    """
    archive = work_dir / "head.zip"
    extract_root = work_dir / "head"
    _run(["git", "archive", "--format=zip", "-o", str(archive), "HEAD"], cwd=repo_root)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extract_root)
    archive.unlink()
    return extract_root


def _build_root_wheel(build_root: Path, work_dir: Path, uv: str) -> Path:
    """Build the command-bearing wheel and assert split-owned binaries stay external."""
    wheel_dir = work_dir / "wheel"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    _run([uv, "build", "--wheel", "--out-dir", str(wheel_dir)], cwd=build_root)
    wheels = sorted(wheel_dir.glob("cadrumo-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one Cadrumo wheel in {wheel_dir}; got {[w.name for w in wheels]!r}")
    with zipfile.ZipFile(wheels[0]) as bundle:
        leaked = [
            name
            for name in bundle.namelist()
            if name.startswith("cadrumo/_data/corpus/") and name.lower().endswith(_CORPUS_BINARY_SUFFIXES)
        ]
    if leaked:
        raise SystemExit(f"root wheel leaked {len(leaked)} corpus source binaries; first ten: {leaked[:10]!r}")
    return wheels[0]


# The two corpus companions and the wheel glob each emits, in install order.
_DATA_COMPANIONS = (
    ("cadrumo_data_manuals", "cadrumo_data_manuals-*.whl"),
    ("cadrumo_data_official", "cadrumo_data_official-*.whl"),
)

# PyPI's default per-file size cap, in the decimal-MB convention the publish and
# CI artifact guards use. The split exists to keep each companion sub-cap.
_PYPI_FILE_CAP_BYTES = 100 * 1_000_000


def _venv_cadrumo(venv: Path) -> Path:
    """Return the installed canonical Cadrumo console script."""
    executable = "aeat.exe" if sys.platform == "win32" else "aeat"
    return _venv_bin(venv) / executable


def _runtime_env(work_dir: Path, state_name: str) -> dict[str, str]:
    """Return a host-independent environment for an installed runtime probe."""
    state_root = work_dir / state_name
    return {
        **_clean_product_env(),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(state_root),
        "CADRUMO_DATABASE_URL": f"sqlite:///{(state_root / 'cadrumo.db').as_posix()}",
    }


def _build_data_wheels(build_root: Path, work_dir: Path, uv: str) -> list[Path]:
    """Build both ``cadrumo-data-*`` companion wheels from their in-repo projects.

    Each companion wheel is asserted sub-cap here too: a companion that crossed
    PyPI's 100 MB per-file limit would defeat the entire reason for the split.
    """
    out_dir = work_dir / "dist-data"
    wheels: list[Path] = []
    for project_dir, wheel_glob in _DATA_COMPANIONS:
        _run(
            [uv, "build", "--project", str(build_root / "packaging" / project_dir), "--out-dir", str(out_dir)],
            cwd=build_root,
        )
        built = sorted(out_dir.glob(wheel_glob))
        if len(built) != 1:
            raise SystemExit(f"expected exactly one {wheel_glob} in {out_dir}, found {built!r}")
        wheel = built[0]
        size_mb = wheel.stat().st_size / 1_000_000
        print(f"  {wheel.name}: {size_mb:.1f} MB", flush=True)
        if wheel.stat().st_size >= _PYPI_FILE_CAP_BYTES:
            raise SystemExit(
                f"{wheel.name} is {size_mb:.1f} MB, at or over PyPI's 100 MB per-file cap; the split must keep "
                "each companion sub-cap"
            )
        wheels.append(wheel)
    return wheels


def _install_cohort_with_pip(work_dir: Path, wheel: Path, data_wheels: list[Path], venv_path: Path) -> None:
    """Install the three local wheels in one pip transaction and validate dependencies."""
    python = _venv_python(venv_path)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            str(wheel.resolve()),
            *(str(data_wheel.resolve()) for data_wheel in data_wheels),
        ],
        cwd=work_dir,
    )
    _run([str(python), "-m", "pip", "check"], cwd=work_dir)


def _assert_registry_verify_runs_clean(work_dir: Path, venv_path: Path) -> None:
    """With the complete cohort installed, full source verification runs clean."""
    _run(
        [str(_venv_cadrumo(venv_path)), "app", "registry", "verify"],
        cwd=work_dir,
        env=_runtime_env(work_dir, "clean-verify-state"),
    )


def main(argv: list[str] | None = None) -> int:
    """Run the three-wheel cohort packaging smoke gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        default=f"{sys.version_info.major}.{sys.version_info.minor}",
        help="Expected Python major.minor for the stdlib venv.",
    )
    parser.add_argument("--work-dir", help="Empty directory for wheels, venv, and artifacts.")
    parser.add_argument(
        "--cohort-dir",
        required=True,
        type=Path,
        help="Directory containing the prebuilt immutable Python cohort.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    work_dir = _work_dir(repo_root, args.work_dir, prefix="split")
    print(f"three-wheel cohort packaging smoke work dir: {work_dir}", flush=True)

    cohort = load_python_cohort(args.cohort_dir)
    wheel = cohort.root_wheel
    data_wheels = list(cohort.companion_wheels)
    print("using supplied immutable Python cohort", flush=True)

    print("creating stdlib venv and installing the complete three-wheel cohort", flush=True)
    venv_path = _create_pip_venv(work_dir, args.python)
    _install_cohort_with_pip(work_dir, wheel, data_wheels, venv_path)
    assert_installed_cohort(
        _venv_python(venv_path),
        cohort,
        root_artifact=wheel,
        cwd=work_dir,
    )

    print("verifying exact dependency cohort and byte-identical source authority", flush=True)
    _run(
        [str(_venv_python(venv_path)), "-c", _COHORT_PROBE],
        cwd=work_dir,
        env=_runtime_env(work_dir, "cohort-import-state"),
    )
    _assert_registry_verify_runs_clean(work_dir, venv_path)
    tax_evidence = run_installed_tax_oracle(
        _venv_cadrumo(venv_path),
        storage_root=work_dir / "tax-oracle-state",
        work_dir=work_dir / "outside-checkout",
    )
    tax_evidence_path = work_dir / "installed-tax-oracle.json"
    tax_evidence_path.write_text(
        json.dumps(tax_evidence.to_jsonable(), indent=2, sort_keys=True) + "\n",
        encoding=_UTF_8,
    )

    manifest = _write_smoke_manifest(
        work_dir,
        lane="three-wheel-cohort",
        artifacts={
            "wheel": _manifest_path(work_dir, wheel),
            "data_wheel_manuals": _manifest_path(work_dir, data_wheels[0]),
            "data_wheel_official": _manifest_path(work_dir, data_wheels[1]),
            "installed_tax_oracle": _manifest_path(work_dir, tax_evidence_path),
            "venv": _manifest_path(work_dir, venv_path),
        },
        checks=(
            "supplied immutable Python cohort",
            "root wheel sheds split-owned corpus binaries",
            "both cadrumo-data-* companion wheels remain sub-cap (< 100 MB each)",
            "stdlib venv creation",
            "all three local wheels install in one pip transaction",
            "pip dependency check",
            "all installed origins and digests match the supplied cohort",
            "root metadata declares both exact mandatory companion requirements",
            "all three installed distributions share one version",
            "joined companion namespace resolves the complete corpus",
            "registry verify runs byte-exact clean",
            "installed grounded Modelo 200 tax-work oracle",
        ),
        details={
            "cohort_version": cohort.version,
            "python": args.python,
            "target_casilla": tax_evidence.target_casilla,
            "target_value": tax_evidence.target_value,
        },
    )

    joined = " + ".join(str(w) for w in (wheel, *data_wheels))
    print(f"three-wheel cohort packaging smoke passed: {joined}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
