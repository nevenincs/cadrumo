"""Build every Cadrumo release artifact once from one clean Git snapshot."""

from __future__ import annotations

import argparse
import inspect
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Final, cast

from dev._paths import UTF_8

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
_SOURCE_ROOT = _REPO_ROOT / "src"
for _import_root in (str(_REPO_ROOT), str(_SOURCE_ROOT)):
    if _import_root not in sys.path:
        sys.path.insert(0, _import_root)
if not __package__:
    __package__ = "dev.packaging"

from cadrumo.core import scan_directory  # noqa: E402

from ._hashing import sha256_path  # noqa: E402
from .cohort_manifest import (  # noqa: E402
    ArtifactKind,
    BuildIdentity,
    LoadedReleaseCohort,
    SourceIdentity,
    create_manifest,
    load_release_cohort,
    write_manifest,
)
from .python_cohort import (  # noqa: E402
    PythonCohort,
    build_python_cohort,
    source_snapshot_drift,
)

_UTF_8: Final[str] = UTF_8
_ZIP_TIMESTAMP: Final[tuple[int, int, int, int, int, int]] = (1980, 1, 1, 0, 0, 0)
_RELEASE_BASE: Final[str] = "https://github.com/nevenincs/cadrumo/releases/download"
_REQUIRED_PYTHON_VERSION: Final[str] = (_REPO_ROOT / ".python-version").read_text(encoding=UTF_8).strip()
_BUILD_CONSTRAINTS: Final[Path] = Path("packaging/build-system-constraints.txt")


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(  # noqa: S603 - explicit repository-owned tool argv.
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="strict",
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"command failed ({completed.returncode}): {argv!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
    return completed


def _git(repo: Path, *args: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise SystemExit("git is required to construct the release cohort")
    return _run([git, *args], cwd=repo).stdout.strip()


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


def _materialise_claude_artifacts(
    *,
    cohort: PythonCohort,
    output: Path,
    work_root: Path,
) -> tuple[Path, Path]:
    from cadrumo_harness import materialise_marketplace

    claude_dir = output / "claude"
    marketplace_tree = work_root / "marketplace"
    # PythonCohort satisfies the runtime protocol exactly. The public materialiser
    # annotates its mutable ``dict`` digest field as a read-only Mapping protocol,
    # which static structural typing cannot prove for a frozen dataclass.
    plugin_cohort = cast("Any", cohort)
    marketplace_manifest = materialise_marketplace(
        marketplace_tree,
        cohort=plugin_cohort,
    )
    plugin_source = PurePosixPath(marketplace_manifest.plugin_source.removeprefix("./"))
    plugin_tree = marketplace_tree / plugin_source
    if not plugin_tree.is_dir():
        raise SystemExit(
            f"marketplace did not materialise its declared plugin source: {plugin_source}",
        )
    plugin = deterministic_zip_tree(
        plugin_tree,
        claude_dir / f"cadrumo-plugin-{cohort.version}.zip",
    )
    marketplace = deterministic_zip_tree(
        marketplace_tree,
        claude_dir / f"cadrumo-marketplace-{cohort.version}.zip",
    )
    return plugin, marketplace


def _require_cohort_aware_marketplace_materialiser() -> None:
    """Refuse before building if the clean source cannot embed cohort wheels."""
    from cadrumo_harness import materialise_marketplace

    if "cohort" not in inspect.signature(materialise_marketplace).parameters:
        raise SystemExit(
            "clean source marketplace materialiser cannot embed the immutable Python cohort: "
            "cadrumo_harness.materialise_marketplace accepts no 'cohort' argument, so the built "
            "plugin would ship without pinned wheels. Give it a 'cohort' parameter that it "
            "forwards to materialise_plugin, then re-run release assembly.",
        )


def _generate_channel_artifacts(
    *,
    clean_root: Path,
    cohort: PythonCohort,
    output: Path,
    env: dict[str, str],
) -> tuple[Path, Path, Path]:
    release_base_url = f"{_RELEASE_BASE}/v{cohort.version}"
    scoop = output / "scoop" / "cadrumo.json"
    _run(
        [
            sys.executable,
            str(clean_root / "packaging" / "scoop" / "generate.py"),
            "--cohort-dir",
            str(cohort.directory),
            "--version",
            cohort.version,
            "--release-base-url",
            release_base_url,
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
            "--release-base-url",
            release_base_url,
            "--output-dir",
            str(homebrew_dir),
        ],
        cwd=clean_root,
        env=env,
    )
    mcpb_dir = output / "mcpb"
    _run(
        [
            sys.executable,
            str(clean_root / "packaging" / "mcpb" / "build.py"),
            "--cohort-dir",
            str(cohort.directory),
            "--dist-dir",
            str(mcpb_dir),
        ],
        cwd=clean_root,
        env=env,
    )
    return (
        scoop.resolve(strict=True),
        (homebrew_dir / "Formula" / "cadrumo.rb").resolve(strict=True),
        (mcpb_dir / f"cadrumo-{cohort.version}.mcpb").resolve(strict=True),
    )


def _source_tag(clean_root: Path, *, commit: str, version: str, requested: str | None) -> str | None:
    tags = frozenset(_git(clean_root, "tag", "--points-at", commit).splitlines())
    if requested is not None:
        if requested not in tags:
            raise SystemExit(f"requested source tag {requested!r} does not identify {commit}")
        if requested != f"v{version}":
            raise SystemExit(
                f"source tag {requested!r} does not match cohort version {version!r}",
            )
        return requested
    expected = f"v{version}"
    return expected if expected in tags else None


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
    if platform.python_implementation() != "CPython" or python_version != _REQUIRED_PYTHON_VERSION:
        raise SystemExit(
            "release cohort requires "
            f"CPython {_REQUIRED_PYTHON_VERSION}, got "
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
    expected_commit: str,
    requested_tag: str | None,
) -> LoadedReleaseCohort:
    """Assemble every member in one clean process without rebuilding a lane."""
    root = clean_root.resolve(strict=True)
    if source_snapshot_drift(root):
        raise SystemExit("internal release source clone is not clean")
    commit = _git(root, "rev-parse", "HEAD")
    if commit != expected_commit:
        raise SystemExit(f"clean source commit drifted: expected {expected_commit}, got {commit}")
    output = output_dir.resolve()
    if output.exists():
        raise SystemExit(f"release cohort staging output already exists: {output}")
    output.mkdir(parents=True)

    source_epoch = _git(root, "show", "-s", "--format=%ct", commit)
    builder = _build_identity(root)
    _require_cohort_aware_marketplace_materialiser()
    build_constraints = (root / _BUILD_CONSTRAINTS).resolve(strict=True)
    os.environ["SOURCE_DATE_EPOCH"] = source_epoch
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ["UV_BUILD_CONSTRAINT"] = str(build_constraints)
    os.environ["UV_REQUIRE_HASHES"] = "1"
    os.environ["UV_PYTHON"] = sys.executable
    os.environ["UV_PYTHON_DOWNLOADS"] = "never"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(root / "src"), str(root)))

    python_work = root / "var" / f"release-python-{uuid.uuid4().hex}"
    work_root = root / "var" / f"release-claude-{uuid.uuid4().hex}"
    python_cohort = build_python_cohort(root, python_work)
    cohort = _copy_python_cohort(python_cohort, output / "python")
    work_root.mkdir(parents=True)
    plugin, marketplace = _materialise_claude_artifacts(
        cohort=cohort,
        output=output,
        work_root=work_root,
    )
    scoop, homebrew, mcpb = _generate_channel_artifacts(
        clean_root=root,
        cohort=cohort,
        output=output,
        env=env,
    )
    tag = _source_tag(
        root,
        commit=commit,
        version=cohort.version,
        requested=requested_tag,
    )
    manifest = create_manifest(
        root=output,
        version=cohort.version,
        source=SourceIdentity(commit=commit, tag=tag),
        created_at=datetime.now(UTC),
        builder=builder,
        artifacts=(
            ("cadrumo-wheel", ArtifactKind.PYTHON_WHEEL, cohort.root_wheel),
            ("cadrumo-sdist", ArtifactKind.PYTHON_SDIST, cohort.root_sdist),
            ("cadrumo-harness-wheel", ArtifactKind.PYTHON_WHEEL, cohort.harness_wheel),
            ("cadrumo-harness-sdist", ArtifactKind.PYTHON_SDIST, cohort.harness_sdist),
            (
                "cadrumo-source-archive",
                ArtifactKind.PYTHON_SOURCE_ARCHIVE,
                cohort.source_archive,
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
            ("claude-plugin", ArtifactKind.CLAUDE_PLUGIN, plugin),
            ("claude-marketplace", ArtifactKind.CLAUDE_MARKETPLACE, marketplace),
            ("scoop-manifest", ArtifactKind.SCOOP_MANIFEST, scoop),
            ("homebrew-formula", ArtifactKind.HOMEBREW_FORMULA, homebrew),
            ("mcpb", ArtifactKind.MCPB, mcpb),
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
    expected_commit: str | None = None,
    source_tag: str | None = None,
) -> LoadedReleaseCohort:
    """Clone checked-out HEAD and execute that clean snapshot's builder once."""
    root = repo_root.resolve(strict=True)
    output = _safe_new_output(output_dir, repo_root=root)
    head = _git(root, "rev-parse", "HEAD")
    commit = expected_commit or head
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise SystemExit(f"expected commit must be one lowercase full SHA: {commit!r}")
    if commit != head:
        raise SystemExit(
            f"expected commit does not equal the currently checked-out HEAD: expected {commit}, got {head}",
        )
    var = (root / "var").resolve()
    with tempfile.TemporaryDirectory(prefix="cadrumo-release-") as temporary:
        clean_root = Path(temporary) / "source"
        git = shutil.which("git")
        if git is None:
            raise SystemExit("git is required to construct the release cohort")
        _run(
            [
                git,
                "-c",
                "core.longpaths=true",
                "clone",
                "--no-hardlinks",
                "--quiet",
                str(root),
                str(clean_root),
            ],
            cwd=root,
        )
        cloned_commit = _git(clean_root, "rev-parse", "HEAD")
        if cloned_commit != commit:
            raise SystemExit(
                f"local clean clone resolved {cloned_commit}, expected source commit {commit}",
            )
        staging = var / f".{output.name}-{uuid.uuid4().hex}.staging"
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(clean_root / "src"), str(clean_root)))
        argv = [
            sys.executable,
            str(clean_root / "dev" / "packaging" / "release_cohort.py"),
            "build-clean",
            "--output",
            str(staging),
            "--expected-commit",
            commit,
        ]
        if source_tag is not None:
            argv.extend(("--source-tag", source_tag))
        try:
            _run(argv, cwd=clean_root, env=env)
            staging.replace(output)
        except (OSError, SystemExit):
            if (
                staging.parent == var
                and staging.name.startswith(f".{output.name}-")
                and staging.name.endswith(".staging")
                and staging.exists()
            ):
                shutil.rmtree(staging)
            raise
    cohort = load_release_cohort(output)
    if cohort.manifest.source.commit != commit:
        raise SystemExit("completed release cohort lost its requested source commit")
    return cohort


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--expected-commit")
    build.add_argument("--source-tag")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--cohort-dir", required=True, type=Path)
    clean = subparsers.add_parser("build-clean", help=argparse.SUPPRESS)
    clean.add_argument("--output", required=True, type=Path)
    clean.add_argument("--expected-commit", required=True)
    clean.add_argument("--source-tag")
    return parser


def main() -> int:
    """Build from a clean clone, run the internal assembly, or verify bytes."""
    args = _parser().parse_args()
    if args.command == "build":
        cohort = build_release_cohort(
            repo_root=_REPO_ROOT,
            output_dir=args.output,
            expected_commit=args.expected_commit,
            source_tag=args.source_tag,
        )
    elif args.command == "build-clean":
        cohort = build_from_clean_source(
            clean_root=_REPO_ROOT,
            output_dir=args.output,
            expected_commit=args.expected_commit,
            requested_tag=args.source_tag,
        )
    else:
        cohort = load_release_cohort(args.cohort_dir)
    print(
        json.dumps(
            {
                "cohort_id": cohort.manifest.cohort_id,
                "directory": str(cohort.directory),
                "source_commit": cohort.manifest.source.commit,
                "source_tag": cohort.manifest.source.tag,
                "version": cohort.manifest.version,
            },
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
