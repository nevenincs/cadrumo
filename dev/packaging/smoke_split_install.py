"""Prove the split install: slim wheel degrades loudly, companions restore byte-parity.

The split ships the runtime as a slim ``cadrumo`` wheel with the corpus source
binaries excluded, plus TWO sub-cap companion distributions carrying exactly
those binaries between them: ``cadrumo-data-manuals`` (``corpus/manuals``) and
``cadrumo-data-official`` (``corpus/aeat_official`` + ``corpus/normatives``). Both
contribute subtrees to the SAME ``cadrumo_data`` implicit namespace package, so the
corpus seam resolves a binary from either portion. This lane proves both halves
of the contract in a fresh stdlib venv:

- **Core alone (degraded path):** the installed source catalogue and companion
  resolver expose the missing split-owned set plus the canonical
  ``cadrumo[corpus-sources]`` install hint, and the
  full registry authority remains deferred until its evidence is installed.
- **With both companions (byte-identical path):** the same venv, after
  installing the two ``cadrumo-data-*`` wheels, resolves the binaries through the
  corpus seam over the joined namespace, the advisory disappears, and full
  byte-exact source verification runs clean — behaviour identical to a full
  checkout.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from .smoke_core import (
    _clean_product_env,
    _executable,
    _manifest_path,
    _run,
    _venv_bin,
    _venv_python,
    _work_dir,
    _write_smoke_manifest,
)
from .smoke_pip_core import _create_pip_venv, _install_target_with_pip

_CORPUS_BINARY_SUFFIXES = (".docx", ".pdf", ".xls", ".xlsx", ".zip")

_ADVISORY_PROBE = """
from importlib.resources import files

from cadrumo.core.resources import bundled_path, resolve_companion_binary
from cadrumo.domain.calculations.registry import CORPUS_SOURCES_INSTALL_HINT, load_registry_tree
from cadrumo.entrypoints.cli._errors import CliRefusedBoundaryError
from cadrumo.entrypoints.cli._registry_corpus import refuse_when_corpus_companion_absent

source_root = bundled_path()
_, catalogues = load_registry_tree(source_root.joinpath("registry", "aeat"))
split_suffixes = (".docx", ".pdf", ".xls", ".xlsx", ".zip")
missing = sorted({
    source.corpus_path
    for source in catalogues.sources.values()
    if source.corpus_path.lower().endswith(split_suffixes)
    and not source_root.joinpath(source.corpus_path).is_file()
    and resolve_companion_binary(*source.corpus_path.split("/")) is None
})
if not missing:
    raise SystemExit("expected split-owned corpus binaries to be absent from the slim install")
if not files("cadrumo").joinpath("_data", "corpus", "aeat_official", "instructions").is_dir():
    raise SystemExit("slim wheel lost its non-split official instruction surfaces")

if CORPUS_SOURCES_INSTALL_HINT != "pip install 'cadrumo[corpus-sources]'":
    raise SystemExit(f"unexpected companion install hint: {CORPUS_SOURCES_INSTALL_HINT!r}")
try:
    refuse_when_corpus_companion_absent(capability="registry verification", missing_advisories=tuple(missing))
except CliRefusedBoundaryError as exc:
    if exc.context.get("install") != CORPUS_SOURCES_INSTALL_HINT:
        raise SystemExit(f"unexpected companion refusal context: {exc.context!r}") from exc
else:
    raise SystemExit("production companion boundary did not refuse for the missing split-owned set")
print(f"split-degradation-ok: {len(missing)} missing; {CORPUS_SOURCES_INSTALL_HINT}")
"""

_CLEAN_PROBE = """
import warnings

from cadrumo.domain.calculations.registry import CorpusCompanionAdvisory, bundled_authority

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


def _build_slim_wheel(build_root: Path, work_dir: Path, uv: str) -> Path:
    """Build the slim ``cadrumo`` wheel and assert it sheds every corpus binary."""
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
        raise SystemExit(f"slim wheel leaked {len(leaked)} corpus source binaries; first ten: {leaked[:10]!r}")
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


def _assert_registry_verify_runs_clean(work_dir: Path, venv_path: Path) -> None:
    """With the companion installed, full source verification runs clean."""
    _run(
        [str(_venv_cadrumo(venv_path)), "app", "registry", "verify"],
        cwd=work_dir,
        env=_runtime_env(work_dir, "clean-verify-state"),
    )


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

    print("building slim Cadrumo wheel and both cadrumo-data-* companion wheels", flush=True)
    wheel = _build_slim_wheel(build_root, work_dir, uv)
    data_wheels = _build_data_wheels(build_root, work_dir, uv)

    print("creating stdlib venv and installing the slim wheel ALONE", flush=True)
    venv_path = _create_pip_venv(work_dir, args.python)
    _install_target_with_pip(work_dir, str(wheel.resolve()), venv_path)

    print("degraded path: split absence and remedy detected; full authority remains deferred", flush=True)
    _run(
        [str(_venv_python(venv_path)), "-c", _ADVISORY_PROBE],
        cwd=work_dir,
        env=_runtime_env(work_dir, "advisory-state"),
    )

    print("installing BOTH cadrumo-data-* companions into the same venv", flush=True)
    for data_wheel in data_wheels:
        _install_target_with_pip(work_dir, str(data_wheel.resolve()), venv_path)

    print("byte-identical path: advisory gone; full source verification runs clean", flush=True)
    _run(
        [str(_venv_python(venv_path)), "-c", _CLEAN_PROBE],
        cwd=work_dir,
        env=_runtime_env(work_dir, "clean-import-state"),
    )
    _assert_registry_verify_runs_clean(work_dir, venv_path)

    manifest = _write_smoke_manifest(
        work_dir,
        lane="split-install",
        artifacts={
            "wheel": _manifest_path(work_dir, wheel),
            "data_wheel_manuals": _manifest_path(work_dir, data_wheels[0]),
            "data_wheel_official": _manifest_path(work_dir, data_wheels[1]),
            "venv": _manifest_path(work_dir, venv_path),
        },
        checks=(
            "pristine HEAD extract",
            "slim wheel build sheds every corpus binary",
            "both cadrumo-data-* companion wheels build sub-cap (< 100 MB each)",
            "stdlib venv creation",
            "slim-wheel-only pip install",
            "companion-less source catalogue exposes split absence and canonical remedy "
            "without full authority construction",
            "both companions pip install into one venv (joined namespace)",
            "companion registry load is advisory-free",
            "companion registry verify runs byte-exact clean",
        ),
        details={"python": args.python},
    )

    joined = " + ".join(str(w) for w in (wheel, *data_wheels))
    print(f"split-install packaging smoke passed: {joined}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
