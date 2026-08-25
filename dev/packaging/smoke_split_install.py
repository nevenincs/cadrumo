"""Prove the mandatory three-wheel Cadrumo installation cohort.

The command-bearing ``cadrumo`` wheel excludes large corpus source binaries,
while two exact-version mandatory dependencies carry them:
``cadrumo-data-manuals`` owns ``corpus/manuals`` and
``cadrumo-data-official`` owns ``corpus/aeat_official``, ``corpus/eu_official``,
and ``corpus/normatives``. Both contribute to the same ``cadrumo_data`` implicit
namespace package.

This lane consumes the prebuilt immutable cohort, installs all three wheels
together into a fresh stdlib venv, proves their versions and root metadata form
one exact cohort, and runs full byte-exact registry verification. There is no
supported command-bearing installation without both data distributions.

The root wheel's corpus-binary shedding and each companion's sub-cap size are
enforced where the wheels are BUILT (``python_cohort``), not here. Tests that
need to construct a cohort from source build it with
:func:`~dev.packaging._smoke_common.build_wheel` and
:func:`~dev.packaging._smoke_common.build_companion_wheels`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .._paths import REPO_ROOT
from ._smoke_common import (
    create_pip_venv,
    isolated_product_env,
    record_proof,
    relative_manifest_path,
    resolve_work_dir,
    run_checked,
    venv_cadrumo_path,
    venv_python_path,
    write_smoke_manifest,
)
from .python_cohort import assert_installed_cohort, load_python_cohort

_COHORT_PROBE = """
from importlib.metadata import requires, version

from cadrumo.domain.calculations.registry.authority import bundled_authority

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


def _install_cohort_with_pip(work_dir: Path, wheel: Path, data_wheels: Sequence[Path], venv_path: Path) -> None:
    """Install the three local wheels in one pip transaction and validate dependencies."""
    python = venv_python_path(venv_path)
    run_checked(
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
    run_checked([str(python), "-m", "pip", "check"], cwd=work_dir)


def _assert_registry_verify_runs_clean(work_dir: Path, venv_path: Path) -> None:
    """With the complete cohort installed, full source verification runs clean."""
    run_checked(
        [str(venv_cadrumo_path(venv_path)), "app", "registry", "verify"],
        cwd=work_dir,
        env=isolated_product_env(work_dir / "clean-verify-state"),
    )
    record_proof("registry verify runs byte-exact clean")


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

    repo_root = REPO_ROOT
    work_dir = resolve_work_dir(repo_root, args.work_dir, prefix="split")
    print(f"three-wheel cohort packaging smoke work dir: {work_dir}", flush=True)

    cohort = load_python_cohort(args.cohort_dir)
    wheel = cohort.root_wheel
    data_wheels = list(cohort.companion_wheels)
    print("using supplied immutable Python cohort", flush=True)
    record_proof("supplied immutable Python cohort")

    print("creating stdlib venv and installing the complete three-wheel cohort", flush=True)
    venv_path = create_pip_venv(work_dir, args.python)
    _install_cohort_with_pip(work_dir, wheel, data_wheels, venv_path)
    assert_installed_cohort(
        venv_python_path(venv_path),
        cohort,
        root_artifact=wheel,
        cwd=work_dir,
    )

    print("verifying exact dependency cohort and byte-identical source authority", flush=True)
    run_checked(
        [str(venv_python_path(venv_path)), "-c", _COHORT_PROBE],
        cwd=work_dir,
        env=isolated_product_env(work_dir / "cohort-import-state"),
    )
    record_proof("joined companion namespace resolves the complete corpus")
    _assert_registry_verify_runs_clean(work_dir, venv_path)

    manifest = write_smoke_manifest(
        work_dir,
        lane="three-wheel-cohort",
        artifacts={
            "wheel": relative_manifest_path(work_dir, wheel),
            "data_wheel_manuals": relative_manifest_path(work_dir, data_wheels[0]),
            "data_wheel_official": relative_manifest_path(work_dir, data_wheels[1]),
            "venv": relative_manifest_path(work_dir, venv_path),
        },
        # Every entry below is performed by THIS main(). The root wheel's
        # corpus-binary shedding and the companions' sub-cap are real
        # guarantees, but they are enforced during cohort construction by
        # `python_cohort._validate_wheel_contract`, not here: this lane
        # consumes a prebuilt cohort and never enters the build path, so
        # claiming them would record a proof that did not run. The installed
        # tax oracle is likewise claimed by the `core` lane that runs it.
        declared=(
            "supplied immutable Python cohort",
            "stdlib venv creation",
            "exact local cohort install with pip",
            "pip dependency check",
            "all installed origins and digests match the supplied cohort",
            "root metadata declares both exact mandatory companion requirements",
            "all three installed distributions share one version",
            "joined companion namespace resolves the complete corpus",
            "registry verify runs byte-exact clean",
        ),
        details={
            "cohort_version": cohort.version,
            "python": args.python,
        },
    )

    joined = " + ".join(str(w) for w in (wheel, *data_wheels))
    print(f"three-wheel cohort packaging smoke passed: {joined}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
