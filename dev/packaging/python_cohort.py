"""Build, load, and verify one immutable local Python distribution cohort."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import Any, Final

from packaging.requirements import Requirement

from cadrumo.core import scan_directory
from dev._paths import REPO_ROOT, UTF_8

from ._distribution_limits import PYPI_FILE_CAP_BYTES
from ._distribution_names import normalise_distribution_name
from ._hashing import sha256_path
from ._proof_ledger import record_proof

_UTF_8: Final[str] = UTF_8
_MANIFEST_NAME: Final[str] = "python-cohort.json"

# ``uv build --out-dir`` writes a one-byte ``.gitignore`` (containing ``*``) into
# its output directory, so the cohort directory acquires a file no manifest can
# declare. It is build-tool bookkeeping, never an installable artifact, and is
# excluded by exact name: the closed-world inventory below must keep refusing any
# unmanifested wheel or sdist, which a broader pattern would stop doing.
_BUILD_TOOL_EMITTED_FILES: Final[frozenset[str]] = frozenset({".gitignore"})
_BUILD_TREE_SOURCE_DIR: Final[str] = "src"
_WHEEL_REGISTRY_ROOT: Final[str] = "cadrumo/_data/registry/aeat"
"""Where the registry tree sits inside the wheel. A packaging fact, owned here.

Deliberately only the ROOT. What the stamped records beside it are called, and
that they sit beside rather than within, belong to the registry package's
identity module, and are read from it below rather than respelled — a second
spelling is how the build comes to write a name the runtime never looks for.
"""


def cohort_stamped_wheel_data_paths() -> frozenset[str]:
    """Return the wheel-relative data members a cohort build stamps in.

    ``_stamp_bundled_registry_records_into_build_tree`` writes the install-stable
    registry identity and its verdict into the extracted build tree before
    ``uv build``, so a cohort wheel carries data members that no tracked source
    path can account for. The wheel payload check derives its expectation from
    tracked sources, so it must union this set for a cohort wheel — a plain
    ``uv build`` wheel is never stamped and stays strictly tracked-only.

    Derived by asking the registry package where it puts each record, so a
    rename or a relocation there moves this expectation automatically instead of
    surfacing as an ``unexpected`` wheel member in CI. Pinned against a real
    stamp by ``test_cohort_stamped_paths.py``.

    Returns:
        The wheel-relative paths of every stamped member.
    """
    from cadrumo.domain.calculations.registry import (
        registry_identity_stamp_location,
        shipped_verdict_location,
    )

    root = PurePosixPath(_WHEEL_REGISTRY_ROOT)
    return frozenset(
        locate(Path(root.as_posix())).as_posix()
        for locate in (registry_identity_stamp_location, shipped_verdict_location)
    )


def __getattr__(name: str) -> object:
    """Resolve ``COHORT_STAMPED_WHEEL_DATA_PATHS`` lazily.

    Kept as a module attribute so its consumers read unchanged, but resolved on
    access rather than at import. Deriving it reaches the registry facade, which
    is a heavy import this module otherwise takes only inside the one function
    that needs it; binding the value at import time would pull the whole
    registry package into every tool that merely reads a cohort manifest.
    """
    if name == "COHORT_STAMPED_WHEEL_DATA_PATHS":
        return cohort_stamped_wheel_data_paths()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_DISTRIBUTIONS: Final[tuple[str, ...]] = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)
_INSTALLED_PROBE: Final[str] = """
import json
from importlib.metadata import distribution

names = ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official")
items = {name: distribution(name) for name in names}
print(json.dumps({
    "versions": {name: item.version for name, item in items.items()},
    "direct_urls": {
        name: json.loads(item.read_text("direct_url.json") or "null")
        for name, item in items.items()
    },
    "root_requirements": list(items["cadrumo"].requires or ()),
}, sort_keys=True))
"""


@dataclass(frozen=True)
class PythonCohort:
    """One root wheel/sdist and two mandatory data wheel/sdist pairs."""

    directory: Path
    manifest: Path
    source_commit: str
    version: str
    root_wheel: Path
    root_sdist: Path
    manuals_wheel: Path
    manuals_sdist: Path
    official_wheel: Path
    official_sdist: Path
    sha256: dict[str, str]

    @property
    def companion_wheels(self) -> tuple[Path, Path]:
        """Return the mandatory data wheels in stable install order."""
        return (self.manuals_wheel, self.official_wheel)


def _run(argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(  # noqa: S603 - argv is an explicit internal build command.
        argv,
        cwd=cwd,
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


def _single(directory: Path, pattern: str, *, label: str) -> Path:
    matches = scan_directory(directory, pattern=pattern)
    if len(matches) != 1:
        raise SystemExit(
            f"expected exactly one {label} matching {pattern!r} in {directory}; "
            f"got {[path.name for path in matches]!r}",
        )
    return matches[0].resolve(strict=True)


def _wheel_identity(wheel: Path) -> tuple[str, str, tuple[str, ...]]:
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = tuple(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        if len(metadata_names) != 1:
            raise SystemExit(
                f"expected one METADATA member in {wheel}; got {metadata_names!r}",
            )
        metadata = Parser().parsestr(archive.read(metadata_names[0]).decode(_UTF_8))
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise SystemExit(f"wheel metadata lacks Name or Version: {wheel}")
    return (
        normalise_distribution_name(name),
        version,
        tuple(metadata.get_all("Requires-Dist") or ()),
    )


def _sdist_identity(sdist: Path) -> tuple[str, str, tuple[str, ...]]:
    try:
        with tarfile.open(sdist, mode="r:gz") as archive:
            metadata_names = tuple(member for member in archive.getmembers() if member.name.endswith("/PKG-INFO"))
            if len(metadata_names) != 1:
                raise SystemExit(
                    f"expected one PKG-INFO member in {sdist}; got {[member.name for member in metadata_names]!r}",
                )
            handle = archive.extractfile(metadata_names[0])
            if handle is None:
                raise SystemExit(f"could not read PKG-INFO from {sdist}")
            metadata = Parser().parsestr(handle.read().decode(_UTF_8))
    except (tarfile.TarError, UnicodeDecodeError) as exc:
        raise SystemExit(f"invalid source distribution {sdist}: {exc}") from exc
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise SystemExit(f"sdist metadata lacks Name or Version: {sdist}")
    return (
        normalise_distribution_name(name),
        version,
        tuple(metadata.get_all("Requires-Dist") or ()),
    )


def _validate_companion_pins(
    requirements: tuple[str, ...],
    *,
    version: str,
    artifact_kind: str,
) -> None:
    parsed = tuple(Requirement(row) for row in requirements)
    for companion in _DISTRIBUTIONS[1:]:
        matches = tuple(
            requirement for requirement in parsed if normalise_distribution_name(requirement.name) == companion
        )
        if len(matches) != 1:
            raise SystemExit(
                f"root {artifact_kind} must declare exactly one dependency on {companion}",
            )
        requirement = matches[0]
        if requirement.extras or requirement.marker is not None or str(requirement.specifier) != f"=={version}":
            raise SystemExit(
                f"root {artifact_kind} must require {companion}=={version} "
                f"unconditionally and without extras; found {requirement}",
            )


def _validate_wheel_contract(
    root_wheel: Path,
    manuals_wheel: Path,
    official_wheel: Path,
) -> str:
    root_name, version, requirements = _wheel_identity(root_wheel)
    manuals_name, manuals_version, _ = _wheel_identity(manuals_wheel)
    official_name, official_version, _ = _wheel_identity(official_wheel)
    observed = {
        root_name: version,
        manuals_name: manuals_version,
        official_name: official_version,
    }
    if observed != {name: version for name in _DISTRIBUTIONS}:
        raise SystemExit(
            "Python cohort distribution identities or versions drifted: "
            f"expected {{name: {version!r} for name in {_DISTRIBUTIONS!r}}}, got {observed!r}",
        )
    _validate_companion_pins(
        requirements,
        version=version,
        artifact_kind="wheel",
    )
    for wheel in (root_wheel, manuals_wheel, official_wheel):
        if wheel.stat().st_size >= PYPI_FILE_CAP_BYTES:
            raise SystemExit(
                f"{wheel.name} exceeds PyPI's 100 MB per-file cap: {wheel.stat().st_size} bytes",
            )
    return version


def _validate_sdist_contract(
    root_sdist: Path,
    manuals_sdist: Path,
    official_sdist: Path,
    *,
    expected_version: str,
) -> None:
    root_name, root_version, requirements = _sdist_identity(root_sdist)
    manuals_name, manuals_version, _ = _sdist_identity(manuals_sdist)
    official_name, official_version, _ = _sdist_identity(official_sdist)
    observed = {
        root_name: root_version,
        manuals_name: manuals_version,
        official_name: official_version,
    }
    expected = {name: expected_version for name in _DISTRIBUTIONS}
    if observed != expected:
        raise SystemExit(
            f"Python cohort sdist identities or versions drifted: expected {expected!r}, got {observed!r}",
        )
    _validate_companion_pins(
        requirements,
        version=expected_version,
        artifact_kind="sdist",
    )
    for sdist in (root_sdist, manuals_sdist, official_sdist):
        if sdist.stat().st_size >= PYPI_FILE_CAP_BYTES:
            raise SystemExit(
                f"{sdist.name} exceeds PyPI's 100 MB per-file cap: {sdist.stat().st_size} bytes",
            )


def _safe_recreate(directory: Path, *, repo_root: Path) -> None:
    resolved_repo = repo_root.resolve(strict=True)
    resolved_var = (resolved_repo / "var").resolve()
    resolved = directory.resolve()
    if resolved_var not in resolved.parents:
        raise SystemExit(f"cohort output must stay under {resolved_var}: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def source_snapshot_drift(repo_root: Path) -> tuple[str, ...]:
    """Return tracked, staged, or untracked source drift excluded from ``HEAD``."""
    completed = _run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo_root,
    )
    return tuple(line for line in completed.stdout.splitlines() if line.strip())


def _stamp_bundled_registry_records_into_build_tree(build_root: Path) -> frozenset[str]:
    """Stamp the install-stable registry identity and verdict into the wheel tree.

    Written before ``uv build`` so the cadrumo wheel ships both records beside
    the registry tree: the identity lets a matching install establish which tree
    it has without walking seventeen thousand files, and the verdict — keyed on
    that identity — lets it skip runtime registry validation on its very first
    touch. Computed against the extracted build tree, which is byte-identical to
    what the wheel packages, so the install-stable key matches at runtime.

    Both records come from ONE call into the registry package's own release
    stamper. This function derives neither the digest, the filenames, nor the
    locations: doing any of that here would be a second derivation that could
    drift from what the runtime reads, which is exactly the failure the single
    canonical identity module exists to prevent.

    Returns:
        The wheel-relative paths of the stamped members, as the archive carries them.
    """
    from cadrumo import __version__
    from cadrumo.domain.calculations.registry import stamp_bundled_registry_release

    source_root = build_root / _BUILD_TREE_SOURCE_DIR
    registry_root = source_root / "cadrumo" / "_data" / "registry" / "aeat"
    stamped = stamp_bundled_registry_release(registry_root, package_version=__version__)
    resolved_source_root = source_root.resolve()
    return frozenset(
        path.relative_to(resolved_source_root).as_posix() for path in (stamped.identity_path, stamped.verdict_path)
    )


def build_python_cohort(repo_root: Path, output_dir: Path) -> PythonCohort:
    """Build one clean-commit cohort and write its immutable digest manifest."""
    root = repo_root.resolve(strict=True)
    output = output_dir.resolve()
    drift = source_snapshot_drift(root)
    if drift:
        raise SystemExit(
            "immutable cohort construction requires a clean source snapshot; "
            f"commit or remove drift before building: {drift[:20]!r}",
        )
    _safe_recreate(output, repo_root=root)
    source_commit = _run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    if len(source_commit) != 40:
        raise SystemExit(f"git returned an invalid source commit: {source_commit!r}")

    build_root = output.parent / f".{output.name}-source"
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)
    archive = output.parent / f".{output.name}-source.zip"
    if archive.exists():
        archive.unlink()
    try:
        _run(
            ["git", "archive", "--format=zip", "-o", str(archive), source_commit],
            cwd=root,
        )
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(build_root)  # noqa: S202 - archive is produced by local Git.
        _stamp_bundled_registry_records_into_build_tree(build_root)
        uv = shutil.which("uv")
        if uv is None:
            raise SystemExit("uv is required to build the Python cohort")
        _run([uv, "build", "--wheel", "--sdist", "--out-dir", str(output)], cwd=build_root)
        _run(
            [
                uv,
                "build",
                "--wheel",
                "--sdist",
                "--project",
                str(build_root / "packaging" / "cadrumo_data_manuals"),
                "--out-dir",
                str(output),
            ],
            cwd=build_root,
        )
        _run(
            [
                uv,
                "build",
                "--wheel",
                "--sdist",
                "--project",
                str(build_root / "packaging" / "cadrumo_data_official"),
                "--out-dir",
                str(output),
            ],
            cwd=build_root,
        )
    finally:
        if archive.exists():
            archive.unlink()
        if build_root.exists():
            shutil.rmtree(build_root)

    # uv seeds its --out-dir with a `.gitignore`; that is a build-tool artifact,
    # not a cohort member, and the release-cohort completeness check refuses any
    # file the manifest does not declare.
    uv_gitignore = output / ".gitignore"
    if uv_gitignore.exists():
        uv_gitignore.unlink()

    root_wheel = _single(output, "cadrumo-*.whl", label="cadrumo wheel")
    root_sdist = _single(output, "cadrumo-*.tar.gz", label="cadrumo sdist")
    manuals_wheel = _single(
        output,
        "cadrumo_data_manuals-*.whl",
        label="manuals wheel",
    )
    official_wheel = _single(
        output,
        "cadrumo_data_official-*.whl",
        label="official wheel",
    )
    manuals_sdist = _single(
        output,
        "cadrumo_data_manuals-*.tar.gz",
        label="manuals sdist",
    )
    official_sdist = _single(
        output,
        "cadrumo_data_official-*.tar.gz",
        label="official sdist",
    )
    version = _validate_wheel_contract(
        root_wheel,
        manuals_wheel,
        official_wheel,
    )
    _validate_sdist_contract(
        root_sdist,
        manuals_sdist,
        official_sdist,
        expected_version=version,
    )
    artifacts = {
        "cadrumo": root_wheel.name,
        "cadrumo-sdist": root_sdist.name,
        "cadrumo-data-manuals": manuals_wheel.name,
        "cadrumo-data-manuals-sdist": manuals_sdist.name,
        "cadrumo-data-official": official_wheel.name,
        "cadrumo-data-official-sdist": official_sdist.name,
    }
    sha256 = {name: sha256_path(output / filename) for name, filename in artifacts.items()}
    manifest = output / _MANIFEST_NAME
    manifest.write_text(
        json.dumps(
            {
                "artifacts": artifacts,
                "sha256": sha256,
                "source_commit": source_commit,
                "version": version,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    return load_python_cohort(output)


def load_python_cohort(directory: Path) -> PythonCohort:
    """Load a cohort manifest and fail on any identity, path, or digest drift."""
    cohort_dir = directory.resolve(strict=True)
    manifest = cohort_dir / _MANIFEST_NAME
    document = json.loads(manifest.read_text(encoding=_UTF_8))
    if not isinstance(document, dict):
        raise SystemExit("Python cohort manifest must be a JSON object")
    artifacts = document.get("artifacts")
    sha256 = document.get("sha256")
    source_commit = document.get("source_commit")
    version = document.get("version")
    if (
        not isinstance(artifacts, dict)
        or not isinstance(sha256, dict)
        or not isinstance(source_commit, str)
        or len(source_commit) != 40
        or not isinstance(version, str)
        or not version
    ):
        raise SystemExit(f"Python cohort manifest has an invalid schema: {document!r}")
    expected_keys = {
        "cadrumo",
        "cadrumo-sdist",
        "cadrumo-data-manuals",
        "cadrumo-data-manuals-sdist",
        "cadrumo-data-official",
        "cadrumo-data-official-sdist",
    }
    if set(artifacts) != expected_keys or set(sha256) != expected_keys:
        raise SystemExit(
            f"Python cohort manifest keys drifted: artifacts={set(artifacts)!r}, sha256={set(sha256)!r}",
        )

    # The cohort directory is a closed world: the manifest plus exactly the
    # artifacts it declares. An unmanifested file is refused here -- before any
    # per-artifact digest work -- for the same reason ``load_release_cohort``
    # compares the inventory first: an extra file crosses acquisition, smoke,
    # and promote gates unnoticed when only the declared names are checked.
    declared_files = {str(name) for name in artifacts.values()} | {_MANIFEST_NAME}
    observed_files = {
        path.relative_to(cohort_dir).as_posix()
        for path in scan_directory(cohort_dir, recursive=True)
        if path.is_file() and path.name not in _BUILD_TOOL_EMITTED_FILES
    }
    if observed_files != declared_files:
        raise SystemExit(
            f"Python cohort file inventory drifted: "
            f"declared={sorted(declared_files)!r}, observed={sorted(observed_files)!r}",
        )

    resolved: dict[str, Path] = {}
    for name in sorted(expected_keys):
        filename = artifacts[name]
        digest = sha256[name]
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise SystemExit(f"cohort artifact path must be one filename: {filename!r}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise SystemExit(f"cohort artifact digest is invalid for {name!r}: {digest!r}")
        artifact = (cohort_dir / filename).resolve(strict=True)
        if artifact.parent != cohort_dir:
            raise SystemExit(f"cohort artifact escapes its directory: {artifact}")
        actual = sha256_path(artifact)
        if actual != digest:
            raise SystemExit(
                f"cohort artifact digest mismatch for {name!r}: expected {digest}, got {actual}",
            )
        resolved[name] = artifact

    observed_version = _validate_wheel_contract(
        resolved["cadrumo"],
        resolved["cadrumo-data-manuals"],
        resolved["cadrumo-data-official"],
    )
    if observed_version != version:
        raise SystemExit(
            f"cohort manifest version {version!r} != wheel version {observed_version!r}",
        )
    _validate_sdist_contract(
        resolved["cadrumo-sdist"],
        resolved["cadrumo-data-manuals-sdist"],
        resolved["cadrumo-data-official-sdist"],
        expected_version=version,
    )
    return PythonCohort(
        directory=cohort_dir,
        manifest=manifest,
        source_commit=source_commit,
        version=version,
        root_wheel=resolved["cadrumo"],
        root_sdist=resolved["cadrumo-sdist"],
        manuals_wheel=resolved["cadrumo-data-manuals"],
        manuals_sdist=resolved["cadrumo-data-manuals-sdist"],
        official_wheel=resolved["cadrumo-data-official"],
        official_sdist=resolved["cadrumo-data-official-sdist"],
        sha256={str(name): str(digest) for name, digest in sha256.items()},
    )


def digest_install_target(name: str, artifact: Path, *, extras: tuple[str, ...] = ()) -> str:
    """Return one digest-pinned direct URL requirement for a local artifact.

    The ``#sha256=`` fragment makes the installer itself verify the artifact
    bytes at install time and fail closed on drift — installers do not reliably
    record ``archive_info.hashes`` for bare local paths (uv records an empty
    ``archive_info``), so the fragment is the enforceable digest channel.
    """
    resolved = artifact.resolve(strict=True)
    digest = sha256_path(resolved)
    extras_suffix = f"[{','.join(extras)}]" if extras else ""
    return f"{name}{extras_suffix} @ {resolved.as_uri()}#sha256={digest}"


def root_install_target(root_artifact: Path, *, extras: tuple[str, ...] = ()) -> str:
    """Return one digest-pinned direct local root target, optionally with extras."""
    return digest_install_target("cadrumo", root_artifact, extras=extras)


def install_targets(
    cohort: PythonCohort,
    *,
    root_artifact: Path,
    extras: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Return explicit local targets that prevent companion index resolution."""
    return (
        root_install_target(root_artifact, extras=extras),
        digest_install_target("cadrumo-data-manuals", cohort.manuals_wheel),
        digest_install_target("cadrumo-data-official", cohort.official_wheel),
    )


def _verify_direct_urls(
    direct_urls: object,
    cohort: PythonCohort,
    root_artifact: Path,
) -> None:
    """Verify ``direct_url.json`` metadata for every expected cohort member.

    Accepts both uv-style (URL fragment ``#sha256=``) and pip-style
    (``archive_info.hashes``) digest channels, and always re-hashes the origin
    bytes on disk so the proof never rests on installer metadata alone.

    :class:`PythonCohort` holds the expected per-member digests and artifact
    paths that drive the comparison.
    """
    if not isinstance(direct_urls, dict):
        raise SystemExit("installed cohort probe returned no direct URLs")
    expected_artifacts = {
        "cadrumo": root_artifact.resolve(),
        "cadrumo-data-manuals": cohort.manuals_wheel,
        "cadrumo-data-official": cohort.official_wheel,
    }
    for name, artifact in expected_artifacts.items():
        direct_url = direct_urls.get(name)
        recorded_url = direct_url.get("url") if isinstance(direct_url, dict) else None
        base_url, _, fragment = str(recorded_url or "").partition("#")
        if not isinstance(direct_url, dict) or base_url != artifact.as_uri():
            raise SystemExit(
                f"{name} installed from an unrelated origin: {direct_url!r}",
            )
        expected_sha = (
            cohort.sha256["cadrumo-sdist"]
            if name == "cadrumo" and artifact == cohort.root_sdist
            else cohort.sha256[name]
        )
        # Installers differ in where they surface the digest of a local direct
        # install: pip records ``archive_info.hashes`` while uv preserves only
        # the requirement's ``#sha256=`` fragment it verified at install time.
        # Accept either recorded channel, and always re-hash the origin bytes
        # so the proof never rests on installer metadata alone.
        _archive_info = direct_url.get("archive_info")
        _raw_hashes = _archive_info.get("hashes") if isinstance(_archive_info, dict) else None
        _sha_candidate = _raw_hashes.get("sha256") if isinstance(_raw_hashes, dict) else None
        recorded_sha = (
            (_sha_candidate if isinstance(_sha_candidate, str) else None) or fragment.removeprefix("sha256=") or None
        )
        if recorded_sha != expected_sha:
            raise SystemExit(
                f"{name} installed digest drifted: expected {expected_sha}, recorded {recorded_sha!r}",
            )
        origin_sha = sha256_path(artifact.resolve(strict=True))
        if origin_sha != expected_sha:
            raise SystemExit(
                f"{name} origin bytes drifted after install: expected {expected_sha}, hashed {origin_sha}",
            )


def assert_installed_cohort(
    python: Path,
    cohort: PythonCohort,
    *,
    root_artifact: Path,
    cwd: Path,
) -> dict[str, Any]:
    """Prove installed metadata resolves every cohort member from exact local bytes."""
    completed = _run([str(python), "-c", _INSTALLED_PROBE], cwd=cwd)
    document = json.loads(completed.stdout)
    if not isinstance(document, dict):
        raise SystemExit("installed cohort probe did not return a JSON object")
    versions = document.get("versions")
    if versions != {name: cohort.version for name in _DISTRIBUTIONS}:
        raise SystemExit(f"installed cohort versions drifted: {versions!r}")
    requirements = set(document.get("root_requirements") or ())
    expected_requirements = {
        f"cadrumo-data-manuals=={cohort.version}",
        f"cadrumo-data-official=={cohort.version}",
    }
    if not expected_requirements <= requirements:
        raise SystemExit(
            f"installed root metadata lost companion pins: {requirements!r}",
        )
    _verify_direct_urls(document.get("direct_urls"), cohort, root_artifact)
    record_proof("all installed origins and digests match the supplied cohort")
    record_proof("root metadata declares both exact mandatory companion requirements")
    record_proof("all three installed distributions share one version")
    return document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--output", required=True, type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--cohort-dir", required=True, type=Path)
    return parser


def main() -> int:
    """Build or verify one immutable Python cohort."""
    args = _parser().parse_args()
    if args.command == "build":
        cohort = build_python_cohort(REPO_ROOT, args.output)
    else:
        cohort = load_python_cohort(args.cohort_dir)
    print(
        json.dumps(
            {
                "directory": str(cohort.directory),
                "sha256": cohort.sha256,
                "source_commit": cohort.source_commit,
                "version": cohort.version,
            },
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
