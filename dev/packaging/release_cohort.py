"""Build every Cadrumo release artifact once from one clean source snapshot."""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from dev._paths import UTF_8
from dev.packaging.command_execution import CommandResult, run_command

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
_SOURCE_ROOT = _REPO_ROOT / "src"
for _import_root in (str(_REPO_ROOT), str(_SOURCE_ROOT)):
    if _import_root not in sys.path:
        sys.path.insert(0, _import_root)
if not __package__:
    __package__ = "dev.packaging"

scan_directory = importlib.import_module("cadrumo.core.directory_scan").scan_directory
_SOURCE_TREE = importlib.import_module("dev.source_tree")
content_digest = _SOURCE_TREE.content_digest
repository_files = _SOURCE_TREE.repository_files
snapshot = _SOURCE_TREE.snapshot
stage_published_authority = importlib.import_module("dev.packaging.authority_staging").stage_published_authority
_BUILD_SCRATCH = importlib.import_module("dev.packaging.build_scratch_reclaim")
RELEASE_STAGING_FAMILY = _BUILD_SCRATCH.RELEASE_STAGING_FAMILY
matching_family = _BUILD_SCRATCH.matching_family
sweep_var_scratch = _BUILD_SCRATCH.sweep_var_scratch
var_scratch_name = _BUILD_SCRATCH.var_scratch_name
_COHORT_MANIFEST = importlib.import_module("dev.packaging.cohort_manifest")
ArtifactKind = _COHORT_MANIFEST.ArtifactKind
BuildIdentity = _COHORT_MANIFEST.BuildIdentity
LoadedReleaseCohort = _COHORT_MANIFEST.LoadedReleaseCohort
SourceIdentity = _COHORT_MANIFEST.SourceIdentity
create_manifest = _COHORT_MANIFEST.create_manifest
load_release_cohort = _COHORT_MANIFEST.load_release_cohort
write_manifest = _COHORT_MANIFEST.write_manifest
sha256_path = importlib.import_module("dev.packaging.hashing").sha256_path
_PYTHON_COHORT = importlib.import_module("dev.packaging.python_cohort")
PythonCohort = _PYTHON_COHORT.PythonCohort
build_python_cohort = _PYTHON_COHORT.build_python_cohort

_UTF_8: Final[str] = UTF_8
_ZIP_TIMESTAMP: Final[tuple[int, int, int, int, int, int]] = (1980, 1, 1, 0, 0, 0)
# There is no commit timestamp to read once the build source is identified by
# content digest rather than by a version-control revision. Reproducible
# builds only need SOURCE_DATE_EPOCH to be FIXED for one source identity, not
# to be a real wall-clock moment, so this reuses the same deterministic epoch
# `_ZIP_TIMESTAMP` already gives every other archive this module writes
# (1980-01-01T00:00:00Z).
_SOURCE_DATE_EPOCH: Final[str] = "315532800"
REQUIRED_PYTHON_VERSION: Final[str] = (_REPO_ROOT / ".python-version").read_text(encoding=UTF_8).strip()
_BUILD_CONSTRAINTS: Final[Path] = Path("packaging/build-system-constraints.txt")


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> CommandResult:
    completed = run_command(
        argv,
        cwd=cwd,
        environment=env,
        errors="strict",
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"command failed ({completed.returncode}): {argv!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
    return completed


def _safe_new_output(output_dir: Path, *, repo_root: Path) -> Path:
    root = repo_root.resolve(strict=True)
    var = (root / "var").resolve()
    output = output_dir.resolve()
    if output.parent != var and var not in output.parents:
        raise SystemExit(f"release cohort output must stay under {var}: {output}")
    if output.exists():
        raise SystemExit(f"immutable release cohort output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def deterministic_zip_tree(source: Path, destination: Path) -> Path:
    """Archive a real directory tree with stable paths, metadata, and bytes."""
    root = source.resolve(strict=True)
    files = tuple(path for path in scan_directory(root, recursive=True) if path.is_file())
    if not files:
        raise ValueError(f"cannot archive an empty artifact tree: {root}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    with zipfile.ZipFile(
        destination,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return destination.resolve(strict=True)


def _copy_python_cohort(cohort: PythonCohort, destination: Path) -> PythonCohort:
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(cohort.directory, destination)
    from .python_cohort import load_python_cohort

    return load_python_cohort(destination)


def _generate_channel_artifacts(
    *,
    clean_root: Path,
    cohort: PythonCohort,
    output: Path,
    env: dict[str, str],
) -> tuple[Path, Path]:
    scoop = output / "scoop" / "cadrumo.json"
    _run(
        [
            sys.executable,
            str(clean_root / "packaging" / "scoop" / "generate.py"),
            "--cohort-dir",
            str(cohort.directory),
            "--version",
            cohort.version,
            "--output",
            str(scoop),
        ],
        cwd=clean_root,
        env=env,
    )
    homebrew_dir = output / "homebrew"
    _run(
        [
            sys.executable,
            str(clean_root / "packaging" / "homebrew" / "generate.py"),
            "--cohort-dir",
            str(cohort.directory),
            "--lock",
            str(clean_root / "uv.lock"),
            "--version",
            cohort.version,
            "--output-dir",
            str(homebrew_dir),
        ],
        cwd=clean_root,
        env=env,
    )
    return (
        scoop.resolve(strict=True),
        (homebrew_dir / "Formula" / "cadrumo.rb").resolve(strict=True),
    )


def _source_tag(*, version: str, requested: str | None) -> str | None:
    """Return the release tag, when the caller supplied one matching this cohort.

    A tag has no content-digest analog: it names a point in a project's
    history, and this builder reads no history, only the content it was
    given. The caller — the release workflow, which already knows which tag
    it is releasing — supplies the tag it expects; anything else is refused
    rather than guessed.
    """
    if requested is None:
        return None
    if requested != f"v{version}":
        raise SystemExit(
            f"source tag {requested!r} does not match cohort version {version!r}",
        )
    return requested


def _source_commit(requested: str | None) -> str | None:
    """Return the caller-supplied commit the cohort source was checked out at.

    Like the tag, the commit is not read from history: the release workflow
    names the exact commit it checked out, and a malformed identifier is
    refused rather than stamped.
    """
    if requested is None:
        return None
    if re.fullmatch(r"[0-9a-f]{40}", requested) is None:
        raise SystemExit(f"source commit {requested!r} is not a full lowercase commit identifier")
    return requested


def _build_identity(clean_root: Path) -> BuildIdentity:
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required to construct the release cohort")
    uv_version = _run([uv, "--version"], cwd=clean_root).stdout.strip()
    observed_uv = uv_version.split(maxsplit=2)
    # Any uv builds the cohort. The version is RECORDED rather than pinned, so
    # reproducibility is an auditable coordinate instead of a precondition: two
    # cohorts are byte-comparable when their build identities agree, and the
    # identity now says which uv produced each. A hard pin bought that guarantee
    # by refusing to build at all whenever uv moved, which stopped releases on
    # an ordinary toolchain upgrade.
    #
    # The shape is still checked. An unparseable `uv --version` means the probe
    # did not return what we think it did, and stamping that into the manifest
    # would put a fabricated coordinate on every artifact built from it.
    if len(observed_uv) < 2 or observed_uv[0] != "uv":
        raise SystemExit(
            f"could not read a uv version from {uv_version!r}; "
            "the cohort records the build's uv, so an unreadable one cannot be stamped",
        )
    python_version = platform.python_version()
    if platform.python_implementation() != "CPython" or python_version != REQUIRED_PYTHON_VERSION:
        raise SystemExit(
            "release cohort requires "
            f"CPython {REQUIRED_PYTHON_VERSION}, got "
            f"{platform.python_implementation()} {python_version}",
        )
    constraints = (clean_root / _BUILD_CONSTRAINTS).resolve(strict=True)
    return BuildIdentity(
        implementation="dev.packaging.release_cohort",
        format_version=1,
        python=python_version,
        uv=uv_version,
        platform=platform.system(),
        architecture=platform.machine(),
        build_constraints_sha256=sha256_path(constraints),
    )


def build_from_clean_source(
    *,
    clean_root: Path,
    output_dir: Path,
    expected_source_digest: str,
    requested_tag: str | None,
    requested_commit: str | None = None,
) -> LoadedReleaseCohort:
    """Assemble every member in one clean process without rebuilding a lane."""
    root = clean_root.resolve(strict=True)
    commit = _source_commit(requested_commit)
    observed_digest = content_digest(root, repository_files(root))
    if observed_digest != expected_source_digest:
        raise SystemExit(
            f"clean source digest drifted: expected {expected_source_digest}, got {observed_digest}",
        )
    output = output_dir.resolve()
    if output.exists():
        raise SystemExit(f"release cohort staging output already exists: {output}")
    output.mkdir(parents=True)

    builder = _build_identity(root)
    build_constraints = (root / _BUILD_CONSTRAINTS).resolve(strict=True)
    os.environ["SOURCE_DATE_EPOCH"] = _SOURCE_DATE_EPOCH
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ["UV_BUILD_CONSTRAINT"] = str(build_constraints)
    os.environ["UV_REQUIRE_HASHES"] = "1"
    os.environ["UV_PYTHON"] = sys.executable
    os.environ["UV_PYTHON_DOWNLOADS"] = "never"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(root / "src"), str(root)))

    python_work = root / "var" / f"release-python-{uuid.uuid4().hex}"
    python_cohort = build_python_cohort(root, python_work)
    cohort = _copy_python_cohort(python_cohort, output / "python")
    scoop, homebrew = _generate_channel_artifacts(
        clean_root=root,
        cohort=cohort,
        output=output,
        env=env,
    )
    tag = _source_tag(
        version=cohort.version,
        requested=requested_tag,
    )
    manifest = create_manifest(
        root=output,
        version=cohort.version,
        source=SourceIdentity(source_digest=expected_source_digest, tag=tag, commit=commit),
        created_at=datetime.now(UTC),
        builder=builder,
        artifacts=(
            ("cadrumo-wheel", ArtifactKind.PYTHON_WHEEL, cohort.root_wheel),
            ("cadrumo-sdist", ArtifactKind.PYTHON_SDIST, cohort.root_sdist),
            (
                "cadrumo-source-archive",
                ArtifactKind.PYTHON_SOURCE_ARCHIVE,
                cohort.source_archive,
            ),
            (
                "cadrumo-runtime-wheelhouse",
                ArtifactKind.PYTHON_WHEELHOUSE,
                cohort.runtime_wheelhouse,
            ),
            (
                "cadrumo-data-manuals-wheel",
                ArtifactKind.PYTHON_WHEEL,
                cohort.manuals_wheel,
            ),
            (
                "cadrumo-data-manuals-sdist",
                ArtifactKind.PYTHON_SDIST,
                cohort.manuals_sdist,
            ),
            (
                "cadrumo-data-official-wheel",
                ArtifactKind.PYTHON_WHEEL,
                cohort.official_wheel,
            ),
            (
                "cadrumo-data-official-sdist",
                ArtifactKind.PYTHON_SDIST,
                cohort.official_sdist,
            ),
            (
                "python-cohort-manifest",
                ArtifactKind.PYTHON_MANIFEST,
                cohort.manifest,
            ),
            ("scoop-manifest", ArtifactKind.SCOOP_MANIFEST, scoop),
            ("homebrew-formula", ArtifactKind.HOMEBREW_FORMULA, homebrew),
        ),
    )
    write_manifest(output, manifest)
    declared = {record.path for record in manifest.artifacts} | {"release-cohort.json"}
    observed = {
        path.relative_to(output).as_posix() for path in scan_directory(output, recursive=True) if path.is_file()
    }
    if observed != declared:
        raise SystemExit(
            "release cohort contains undeclared or missing files: "
            f"declared={sorted(declared)!r}, observed={sorted(observed)!r}",
        )
    return load_release_cohort(output)


def build_release_cohort(
    *,
    repo_root: Path,
    output_dir: Path,
    source_tag: str | None = None,
    source_commit: str | None = None,
) -> LoadedReleaseCohort:
    """Snapshot the current source tree and execute that clean copy's builder once."""
    root = repo_root.resolve(strict=True)
    _source_commit(source_commit)
    output = _safe_new_output(output_dir, repo_root=root)
    source_files = repository_files(root)
    digest = content_digest(root, source_files)
    var = (root / "var").resolve()
    # A build that is killed leaves its staging directory -- a full cohort's
    # worth of bytes -- behind, and runs no cleanup of its own. The staging name
    # below carries this process as its owner, so a previous build's leftovers
    # are reclaimed here on an observed liveness answer rather than waiting out
    # the day ceiling an operator has to ask for. The start of a build is the
    # only moment that survives a kill.
    with contextlib.suppress(OSError):
        sweep_var_scratch(var)
    with tempfile.TemporaryDirectory(prefix="cadrumo-release-") as temporary:
        clean_root = Path(temporary) / "source"
        # An isolated copy of the enumerated tree, not the live one: the rest
        # of this build runs in a child process against `clean_root`, so a
        # peer's concurrent edit to `root` cannot land inside a build already
        # in flight.
        snapshot(root, source_files, clean_root)
        snapshot_digest = content_digest(clean_root, repository_files(clean_root))
        if snapshot_digest != digest:
            raise SystemExit(
                f"release source snapshot content drifted from its digest: expected {digest}, got {snapshot_digest}",
            )
        # Staged after the drift check, and into the gitignored location the
        # origin keeps it in, so the release identity digest stays a statement
        # about enumerated source and is unaffected by generated payload the
        # build nonetheless has to carry.
        stage_published_authority(root, clean_root)
        staging = var / var_scratch_name(RELEASE_STAGING_FAMILY, f"{output.name}-{uuid.uuid4().hex}")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(clean_root / "src"), str(clean_root)))
        argv = [
            sys.executable,
            "-m",
            "dev.packaging.release_cohort",
            "build-clean",
            "--output",
            str(staging),
            "--expected-source-digest",
            digest,
        ]
        if source_tag is not None:
            argv.extend(("--source-tag", source_tag))
        if source_commit is not None:
            argv.extend(("--source-commit", source_commit))
        try:
            _run(argv, cwd=clean_root, env=env)
            staging.replace(output)
        except (OSError, SystemExit):
            # Judged by the same registry the sweep uses, so the guard cannot
            # drift from the name that was minted a few lines above.
            if staging.parent == var and matching_family(staging.name) is not None and staging.exists():
                shutil.rmtree(staging)
            raise
    cohort = load_release_cohort(output)
    if cohort.manifest.source.source_digest != digest:
        raise SystemExit("completed release cohort lost its requested source digest")
    if cohort.manifest.source.commit != source_commit:
        raise SystemExit("completed release cohort lost its requested source commit")
    return cohort


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--source-tag")
    build.add_argument("--source-commit")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--cohort-dir", required=True, type=Path)
    clean = subparsers.add_parser("build-clean", help=argparse.SUPPRESS)
    clean.add_argument("--output", required=True, type=Path)
    clean.add_argument("--expected-source-digest", required=True)
    clean.add_argument("--source-tag")
    clean.add_argument("--source-commit")
    return parser


def main() -> int:
    """Build from a clean snapshot, run the internal assembly, or verify bytes."""
    args = _parser().parse_args()
    if args.command == "build":
        cohort = build_release_cohort(
            repo_root=_REPO_ROOT,
            output_dir=args.output,
            source_tag=args.source_tag,
            source_commit=args.source_commit,
        )
    elif args.command == "build-clean":
        cohort = build_from_clean_source(
            clean_root=_REPO_ROOT,
            output_dir=args.output,
            expected_source_digest=args.expected_source_digest,
            requested_tag=args.source_tag,
            requested_commit=args.source_commit,
        )
    else:
        cohort = load_release_cohort(args.cohort_dir)
    print(
        json.dumps(
            {
                "cohort_id": cohort.manifest.cohort_id,
                "directory": str(cohort.directory),
                "source_commit": cohort.manifest.source.commit,
                "source_digest": cohort.manifest.source.source_digest,
                "source_tag": cohort.manifest.source.tag,
                "version": cohort.manifest.version,
            },
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
