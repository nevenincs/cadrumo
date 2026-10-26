"""Prove the mandatory four-wheel Cadrumo installation cohort.

The command-bearing ``cadrumo`` wheel excludes large corpus source binaries,
while three exact-version mandatory dependencies carry them:
``cadrumo-data-manuals`` owns ``corpus/manuals`` and
``cadrumo-data-official`` owns ``corpus/aeat_official`` and ``corpus/eu_official``;
``cadrumo-data-normatives`` owns ``corpus/normatives``. All three contribute to the same ``cadrumo_data`` implicit
namespace package.

This lane consumes the prebuilt immutable cohort, installs all four wheels
together into a fresh stdlib venv, proves their versions and root metadata form
one exact cohort, and reads the installed published authority. There is no
supported command-bearing installation without all three data distributions.

The root wheel's corpus-binary shedding and each companion's sub-cap size are
enforced where the wheels are BUILT (``python_cohort``), not here. Tests that
need to construct a cohort from source build it with
:func:`~dev.packaging.lane_verification_core.build_wheel` and
:func:`~dev.packaging.lane_verification_core.build_companion_wheels`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT

from .lane_verification_core import (
    create_pip_venv,
    install_targets_with_pip,
    isolated_product_env,
    relative_manifest_path,
    resolve_work_dir,
    run_checked,
    venv_python_path,
    write_smoke_manifest,
)
from .proof_ledger import record_proof
from .python_cohort import assert_installed_cohort, load_python_cohort

_COHORT_PROBE = """
from importlib.metadata import requires, version
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority


root_version = version("cadrumo")
expected = {
    f"cadrumo-data-manuals=={root_version}",
    f"cadrumo-data-official=={root_version}",
    f"cadrumo-data-normatives=={root_version}",
}
declared = set(requires("cadrumo") or ())
missing_requirements = expected - declared
if missing_requirements:
    raise SystemExit(f"root metadata lost mandatory companion pins: {sorted(missing_requirements)!r}")
for distribution in ("cadrumo-data-manuals", "cadrumo-data-official", "cadrumo-data-normatives"):
    observed = version(distribution)
    if observed != root_version:
        raise SystemExit(f"{distribution} version {observed!r} != root version {root_version!r}")

with bundled_indexed_authority().operation() as authority:
    if not authority.modelo_directory("100").revisions:
        raise SystemExit("installed authority has no modelo 100 revisions")
print(f"four-wheel-cohort-ok: {root_version}")
"""


_INSTALLED_CORPUS_PROBE = """
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from cadrumo.core.resources.bundled_data import resolve_corpus_binary

expected = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not isinstance(expected, dict) or not expected:
    raise SystemExit("installed corpus probe requires a nonempty wheel member census")
for logical_path, digest in expected.items():
    binary = resolve_corpus_binary(*PurePosixPath(logical_path).parts)
    if binary is None:
        raise SystemExit(f"installed corpus binary is missing: {logical_path}")
    actual = hashlib.sha256(binary.read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f"installed corpus bytes drifted: {logical_path} expected {digest}, got {actual}")
print(f"joined-companion-corpus-ok: {len(expected)} verified binary members")
"""


def _companion_corpus_hashes(data_wheels: Sequence[Path]) -> dict[str, str]:
    """Hash every supplied companion corpus member without trusting installed files."""
    if len(data_wheels) != len(PRODUCT_IDENTITY.companion_distributions):
        raise SystemExit("corpus verification requires every mandatory companion wheel")
    prefix = "cadrumo_data/_data/"
    expected: dict[str, str] = {}
    for wheel in data_wheels:
        members = 0
        with zipfile.ZipFile(wheel) as archive:
            for member in archive.infolist():
                if member.is_dir() or not member.filename.startswith(f"{prefix}corpus/"):
                    continue
                logical_path = member.filename.removeprefix(prefix)
                path = PurePosixPath(logical_path)
                if (
                    path.as_posix() != logical_path
                    or any(part in {"", ".", ".."} or ":" in part for part in path.parts)
                    or "\\" in logical_path
                ):
                    raise SystemExit(f"companion corpus member has an unsafe logical path: {logical_path!r}")
                if logical_path in expected:
                    raise SystemExit(f"companion corpus member has duplicate ownership: {logical_path}")
                expected[logical_path] = hashlib.sha256(archive.read(member)).hexdigest()
                members += 1
        if not members:
            raise SystemExit(f"mandatory companion carries no corpus binaries: {wheel.name}")
    return dict(sorted(expected.items()))


def _install_cohort_with_pip(work_dir: Path, wheel: Path, data_wheels: Sequence[Path], venv_path: Path) -> None:
    """Install the four local wheels in one pip transaction and validate dependencies."""
    install_targets_with_pip(
        work_dir,
        (str(wheel.resolve()), *(str(data_wheel.resolve()) for data_wheel in data_wheels)),
        venv_path,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the four-wheel cohort packaging smoke gate."""
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
    print(f"four-wheel cohort packaging smoke work dir: {work_dir}", flush=True)

    cohort = load_python_cohort(args.cohort_dir)
    wheel = cohort.root_wheel
    data_wheels = list(cohort.companion_wheels)
    corpus_hashes = work_dir / "companion-corpus-sha256.json"
    corpus_hashes.write_text(
        json.dumps(_companion_corpus_hashes(data_wheels), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("using supplied immutable Python cohort", flush=True)
    record_proof("supplied immutable Python cohort")

    print("creating stdlib venv and installing the complete four-wheel cohort", flush=True)
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
    run_checked(
        [str(venv_python_path(venv_path)), "-c", _INSTALLED_CORPUS_PROBE, str(corpus_hashes)],
        cwd=work_dir,
        env=isolated_product_env(work_dir / "corpus-import-state"),
    )
    record_proof("joined companion namespace resolves the complete corpus")

    manifest = write_smoke_manifest(
        work_dir,
        lane="four-wheel-cohort",
        artifacts={
            "wheel": relative_manifest_path(work_dir, wheel),
            "data_wheel_manuals": relative_manifest_path(work_dir, data_wheels[0]),
            "data_wheel_official": relative_manifest_path(work_dir, data_wheels[1]),
            "data_wheel_normatives": relative_manifest_path(work_dir, data_wheels[2]),
            "companion_corpus_sha256": relative_manifest_path(work_dir, corpus_hashes),
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
            "root metadata declares all exact mandatory companion requirements",
            "all four installed distributions share one version",
            "joined companion namespace resolves the complete corpus",
        ),
        details={
            "cohort_version": cohort.version,
            "python": args.python,
        },
    )

    joined = " + ".join(str(w) for w in (wheel, *data_wheels))
    print(f"four-wheel cohort packaging smoke passed: {joined}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
