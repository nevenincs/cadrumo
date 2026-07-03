"""Prove the split install: slim wheel degrades loudly, companion restores byte-parity.

The two-distribution split (ADR "Wheel split") ships the runtime as a slim
``aeat`` wheel with the corpus source binaries excluded, plus an ``aeat-data``
companion carrying exactly those binaries. This lane proves both halves of the
contract in a fresh stdlib venv:

- **Core alone (advisory path):** the registry authority loads and validates
  non-fatally while emitting the loud :class:`CorpusCompanionAdvisory` naming
  the missing set and the ``aeat-cli[corpus-sources]`` install hint, and the
  companion-guarded ``aeat app registry verify`` verb refuses instructively.
- **With the companion (byte-identical path):** the same venv, after
  installing the ``aeat-data`` wheel, resolves the binaries through the corpus
  seam, the advisory disappears, and full byte-exact source verification runs
  clean — behaviour identical to a full checkout.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

from .smoke_core import (
    _executable,
    _manifest_path,
    _run,
    _venv_aeat,
    _venv_python,
    _work_dir,
    _write_smoke_manifest,
)
from .smoke_pip_core import _create_pip_venv, _install_target_with_pip

_CORPUS_BINARY_SUFFIXES = (".pdf", ".xls", ".xlsx")

_ADVISORY_PROBE = """
import warnings

from aeat.domain.calculations.registry import CorpusCompanionAdvisory, bundled_authority

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    authority = bundled_authority()
    authority.validate_registry()

advisories = [w for w in caught if issubclass(w.category, CorpusCompanionAdvisory)]
if not advisories:
    raise SystemExit("expected the loud CorpusCompanionAdvisory in a companion-less split install")
message = str(advisories[0].message)
if "aeat-cli[corpus-sources]" not in message:
    raise SystemExit(f"advisory does not name the install hint: {message!r}")
print("split-advisory-ok")
"""

_CLEAN_PROBE = """
import warnings

from aeat.domain.calculations.registry import CorpusCompanionAdvisory, bundled_authority

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    authority = bundled_authority()
    authority.validate_registry()

advisories = [w for w in caught if issubclass(w.category, CorpusCompanionAdvisory)]
if advisories:
    raise SystemExit(f"companion installed but the advisory still fired: {advisories[0].message!s}")
print("split-companion-clean-ok")
"""


def _head_extract(repo_root: Path, work_dir: Path) -> Path:
    """Extract a pristine ``git archive HEAD`` tree to build the lane's wheels from.

    The shared factory worktree carries concurrent campaigns' uncommitted WIP
    (including registry TOML mid-edits) that a tree-built wheel would sweep into
    this lane's registry-validation probes, failing them for reasons outside the
    split contract. Building from the HEAD archive keeps the proof owner-clean;
    on a clean checkout (CI) it is identical to the tree.
    """
    archive = work_dir / "head.zip"
    extract_root = work_dir / "head"
    _run(["git", "archive", "--format=zip", "-o", str(archive), "HEAD"], cwd=repo_root)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extract_root)
    archive.unlink()
    return extract_root


def _build_slim_wheel(build_root: Path, work_dir: Path, uv: str) -> Path:
    """Build the slim ``aeat`` wheel and assert it sheds every corpus binary."""
    wheel_dir = work_dir / "wheel"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    _run([uv, "build", "--wheel", "--out-dir", str(wheel_dir)], cwd=build_root)
    wheels = sorted(wheel_dir.glob("aeat_cli-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one aeat wheel in {wheel_dir}; got {[w.name for w in wheels]!r}")
    with zipfile.ZipFile(wheels[0]) as bundle:
        leaked = [
            name
            for name in bundle.namelist()
            if name.startswith("aeat/_data/corpus/") and name.lower().endswith(_CORPUS_BINARY_SUFFIXES)
        ]
    if leaked:
        raise SystemExit(f"slim wheel leaked {len(leaked)} corpus source binaries; first ten: {leaked[:10]!r}")
    return wheels[0]


def _build_data_wheel(build_root: Path, work_dir: Path, uv: str) -> Path:
    """Build the ``aeat-data`` companion wheel from its in-repo project."""
    out_dir = work_dir / "dist-data"
    _run(
        [uv, "build", "--project", str(build_root / "packaging" / "aeat_data"), "--out-dir", str(out_dir)],
        cwd=build_root,
    )
    wheels = sorted(out_dir.glob("aeat_data-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one aeat-data wheel in {out_dir}, found {wheels!r}")
    return wheels[0]


def _assert_registry_verify_refuses(work_dir: Path, venv_path: Path) -> None:
    """The companion-guarded verification verb refuses instructively without it."""
    completed = subprocess.run(  # noqa: S603 - venv-resolved console script, fixed args
        [str(_venv_aeat(venv_path)), "app", "registry", "verify"],
        cwd=work_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        raise SystemExit("aeat app registry verify unexpectedly succeeded without the companion")
    combined = f"{completed.stdout}\n{completed.stderr}"
    if "corpus-sources" not in combined:
        raise SystemExit(f"registry verify refusal does not cite the corpus-sources install hint:\n{combined}")


def _assert_registry_verify_runs_clean(work_dir: Path, venv_path: Path) -> None:
    """With the companion installed, full source verification runs clean."""
    _run([str(_venv_aeat(venv_path)), "app", "registry", "verify"], cwd=work_dir)


def main(argv: list[str] | None = None) -> int:
    """Run the split-install packaging smoke gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        default=f"{sys.version_info.major}.{sys.version_info.minor}",
        help="Expected Python major.minor for the stdlib venv.",
    )
    parser.add_argument("--work-dir", help="Empty directory for wheels, venv, and artifacts.")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    uv = _executable("uv")
    work_dir = _work_dir(repo_root, args.work_dir, prefix="split")
    print(f"split-install packaging smoke work dir: {work_dir}", flush=True)

    print("extracting pristine HEAD tree for owner-clean wheel builds", flush=True)
    build_root = _head_extract(repo_root, work_dir)

    print("building slim aeat wheel and aeat-data companion wheel", flush=True)
    wheel = _build_slim_wheel(build_root, work_dir, uv)
    data_wheel = _build_data_wheel(build_root, work_dir, uv)

    print("creating stdlib venv and installing the slim wheel ALONE", flush=True)
    venv_path = _create_pip_venv(work_dir, args.python)
    _install_target_with_pip(work_dir, str(wheel.resolve()), venv_path)

    print("advisory path: registry load is loud but non-fatal; verify verb refuses", flush=True)
    _run([str(_venv_python(venv_path)), "-c", _ADVISORY_PROBE], cwd=work_dir)
    _assert_registry_verify_refuses(work_dir, venv_path)

    print("installing the aeat-data companion into the same venv", flush=True)
    _install_target_with_pip(work_dir, str(data_wheel.resolve()), venv_path)

    print("byte-identical path: advisory gone; full source verification runs clean", flush=True)
    _run([str(_venv_python(venv_path)), "-c", _CLEAN_PROBE], cwd=work_dir)
    _assert_registry_verify_runs_clean(work_dir, venv_path)

    manifest = _write_smoke_manifest(
        work_dir,
        lane="split-install",
        artifacts={
            "wheel": _manifest_path(work_dir, wheel),
            "data_wheel": _manifest_path(work_dir, data_wheel),
            "venv": _manifest_path(work_dir, venv_path),
        },
        checks=(
            "pristine HEAD extract",
            "slim wheel build sheds every corpus binary",
            "aeat-data companion wheel build",
            "stdlib venv creation",
            "slim-wheel-only pip install",
            "companion-less registry load emits the loud advisory",
            "companion-less registry verify refuses with the install hint",
            "companion pip install",
            "companion registry load is advisory-free",
            "companion registry verify runs byte-exact clean",
        ),
        details={"python": args.python},
    )

    print(f"split-install packaging smoke passed: {wheel} + {data_wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
